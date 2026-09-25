-- FlyVigilante FAERS 웨어하우스: 원천(raw_*) -> 정제(core_*) -> 신호(sig_*)
-- DuckDB 에서 실행한다. load_quarters.py 로 raw_* 가 채워진 뒤 build_model.py 가 부른다.

------------------------------------------------------------------ 정제 계층
-- 1) FDA 삭제 목록 (모든 분기 누적)
CREATE OR REPLACE TABLE core_deleted AS
SELECT DISTINCT TRY_CAST(caseid AS BIGINT) AS caseid FROM raw_deleted WHERE TRY_CAST(caseid AS BIGINT) IS NOT NULL;

-- 2) 버전 계보: caseid 하나에 여러 primaryid(보고 버전)가 쌓인다
CREATE OR REPLACE TABLE core_case_version AS
SELECT TRY_CAST(primaryid AS BIGINT) AS primaryid,
       TRY_CAST(caseid AS BIGINT)    AS caseid,
       TRY_CAST(caseversion AS INT)  AS caseversion,
       i_f_code, rept_cod, quarter,
       TRY_STRPTIME(fda_dt, '%Y%m%d')::DATE       AS fda_dt,
       TRY_STRPTIME(init_fda_dt, '%Y%m%d')::DATE  AS init_fda_dt,
       TRY_STRPTIME(event_dt, '%Y%m%d')::DATE     AS event_dt,
       CASE age_cod WHEN 'YR' THEN TRY_CAST(age AS DOUBLE)
                    WHEN 'MON' THEN TRY_CAST(age AS DOUBLE)/12
                    WHEN 'WK' THEN TRY_CAST(age AS DOUBLE)/52
                    WHEN 'DY' THEN TRY_CAST(age AS DOUBLE)/365
                    WHEN 'DEC' THEN TRY_CAST(age AS DOUBLE)*10
                    WHEN 'HR' THEN TRY_CAST(age AS DOUBLE)/8760 END AS age_years,
       NULLIF(sex, '') AS sex,
       CASE wt_cod WHEN 'KG' THEN TRY_CAST(wt AS DOUBLE) WHEN 'LBS' THEN TRY_CAST(wt AS DOUBLE)*0.4536 END AS weight_kg,
       NULLIF(occp_cod, '') AS occp_cod,
       NULLIF(reporter_country, '') AS reporter_country,
       NULLIF(occr_country, '') AS occr_country,
       NULLIF(mfr_sndr, '') AS mfr_sndr
FROM raw_demo
WHERE TRY_CAST(primaryid AS BIGINT) IS NOT NULL;

-- 3) 케이스 대표 버전: caseid 마다 최신 버전 하나, FDA 삭제 케이스 제외 (FDA 권고 중복제거 규칙)
CREATE OR REPLACE TABLE core_case AS
SELECT * EXCLUDE (rn) FROM (
  SELECT v.*, row_number() OVER (PARTITION BY caseid
           ORDER BY caseversion DESC NULLS LAST, fda_dt DESC NULLS LAST, primaryid DESC) AS rn
  FROM core_case_version v
) WHERE rn = 1 AND caseid NOT IN (SELECT caseid FROM core_deleted);

-- 4) 약물 정규화: 유효성분(prod_ai) 우선, 없으면 상품명. 대문자, 공백/마침표 정리
CREATE OR REPLACE MACRO norm_drug0(ai, name) AS
  NULLIF(regexp_replace(regexp_replace(upper(trim(COALESCE(NULLIF(trim(ai), ''), name))), '[\.\,;]+$', ''), '\s+', ' ', 'g'), '');
-- 염/수화물 접미사는 같은 성분으로 묶는다 (METFORMIN HYDROCHLORIDE -> METFORMIN). 단독 이름은 건드리지 않는다
CREATE OR REPLACE MACRO norm_drug(ai, name) AS
  trim(regexp_replace(norm_drug0(ai, name),
    '(\S)\s+(HYDROCHLORIDE|HCL|HYDROBROMIDE|SODIUM|POTASSIUM|CALCIUM|MAGNESIUM|CITRATE|TARTRATE|BITARTRATE|MALEATE|SULFATE|SULPHATE|SUCCINATE|MESYLATE|BESYLATE|FUMARATE|ACETATE|PHOSPHATE|DIPROPIONATE|PROPIONATE|BROMIDE|CHLORIDE|TROMETHAMINE|MONOHYDRATE|DIHYDRATE|TRIHYDRATE|HEMIHYDRATE|SESQUIHYDRATE|ANHYDROUS|HYCLATE|DISODIUM|LYSINE|ERBUMINE|TOSYLATE|XINAFOATE|PAMOATE|DECANOATE|ENANTHATE|VALERATE)(\s+(MONOHYDRATE|DIHYDRATE|TRIHYDRATE|HEMIHYDRATE|ANHYDROUS))?($|\\)', '\1\5', 'g'));

-- 2014Q3 이전에는 prod_ai 가 없다. 이후 분기에서 상품명 -> 성분 최빈 대응을 학습해 채운다
CREATE OR REPLACE TABLE ref_drugname_map AS
SELECT drugname, arg_max(ai, n) AS ai, max(n) AS support FROM (
  SELECT upper(trim(drugname)) AS drugname, norm_drug(prod_ai, NULL) AS ai, count(*) AS n
  FROM raw_drug WHERE trim(prod_ai) <> '' AND trim(drugname) <> ''
  GROUP BY 1, 2
) WHERE ai IS NOT NULL GROUP BY drugname HAVING max(n) >= 5;

-- 바이오시밀러 접미사(-DYYB 등 4글자)는 신호 집계를 위해 성분으로 묶는다
CREATE OR REPLACE TABLE core_drug AS
SELECT d.primaryid::BIGINT AS primaryid, TRY_CAST(d.drug_seq AS INT) AS drug_seq, d.role_cod,
       regexp_replace(COALESCE(norm_drug(d.prod_ai, NULL), m.ai, norm_drug(NULL, d.drugname)), '-[A-Z]{4}$', '') AS drug,
       upper(trim(d.drugname)) AS drugname_raw,
       NULLIF(d.route, '') AS route, NULLIF(d.dechal, '') AS dechal, NULLIF(d.rechal, '') AS rechal
FROM raw_drug d
JOIN core_case c ON c.primaryid = TRY_CAST(d.primaryid AS BIGINT)
LEFT JOIN ref_drugname_map m ON m.drugname = upper(trim(d.drugname));

CREATE OR REPLACE TABLE core_reac AS
SELECT DISTINCT r.primaryid::BIGINT AS primaryid, lower(trim(r.pt)) AS pt
FROM raw_reac r
JOIN core_case c ON c.primaryid = TRY_CAST(r.primaryid AS BIGINT)
WHERE trim(r.pt) <> '';

CREATE OR REPLACE TABLE core_outc AS
SELECT DISTINCT o.primaryid::BIGINT AS primaryid, trim(o.outc_cod) AS outc_cod
FROM raw_outc o
JOIN core_case c ON c.primaryid = TRY_CAST(o.primaryid AS BIGINT);

CREATE OR REPLACE TABLE core_indi AS
SELECT DISTINCT i.primaryid::BIGINT AS primaryid, TRY_CAST(i.indi_drug_seq AS INT) AS drug_seq, lower(trim(i.indi_pt)) AS indi_pt
FROM raw_indi i
JOIN core_case c ON c.primaryid = TRY_CAST(i.primaryid AS BIGINT)
WHERE trim(i.indi_pt) NOT IN ('', 'product used for unknown indication');

-- 5) 케이스 단위 중대성 플래그 (ICH E2A: 사망, 생명위협, 입원, 장애, 선천이상, 개입필요, 기타 중요)
CREATE OR REPLACE TABLE core_case_serious AS
SELECT primaryid,
       bool_or(outc_cod = 'DE') AS death,
       bool_or(outc_cod = 'LT') AS life_threat,
       bool_or(outc_cod = 'HO') AS hospital,
       bool_or(outc_cod = 'DS') AS disability,
       bool_or(outc_cod = 'CA') AS congenital,
       bool_or(outc_cod = 'RI') AS intervention,
       bool_or(outc_cod = 'OT') AS other_serious
FROM core_outc GROUP BY primaryid;

------------------------------------------------------------------ 신호 계층
-- 의심약(PS, SS)만 대상으로 케이스-약물-반응 삼중항을 만든다
CREATE OR REPLACE TABLE sig_triplet AS
SELECT DISTINCT d.primaryid, d.drug, r.pt
FROM core_drug d JOIN core_reac r USING (primaryid)
WHERE d.role_cod IN ('PS', 'SS') AND d.drug IS NOT NULL;

CREATE OR REPLACE TABLE sig_drug_n AS
SELECT drug, count(DISTINCT primaryid) AS n_drug FROM sig_triplet GROUP BY drug;
CREATE OR REPLACE TABLE sig_pt_n AS
SELECT pt, count(DISTINCT primaryid) AS n_pt FROM sig_triplet GROUP BY pt;

-- 불균형 분석: PRR, ROR (95% CI), Yates 카이제곱, IC 와 IC025 (BCPNN 근사, Norén 2006)
CREATE OR REPLACE TABLE sig_disproportionality AS
WITH n AS (SELECT count(DISTINCT primaryid)::DOUBLE AS N FROM sig_triplet),
ab AS (
  SELECT t.drug, t.pt, count(*)::DOUBLE AS a, dn.n_drug::DOUBLE AS n_drug, pn.n_pt::DOUBLE AS n_pt
  FROM sig_triplet t JOIN sig_drug_n dn USING (drug) JOIN sig_pt_n pn USING (pt)
  GROUP BY t.drug, t.pt, dn.n_drug, pn.n_pt HAVING count(*) >= 3
),
cells AS (
  SELECT drug, pt, a, n_drug - a AS b, n_pt - a AS c, N - n_drug - n_pt + a AS d, n_drug, n_pt, N,
         n_drug * n_pt / N AS expected
  FROM ab, n
)
SELECT drug, pt, a::BIGINT AS a, b::BIGINT AS b, c::BIGINT AS c, d::BIGINT AS d, expected,
       (a/(a+b)) / (c/(c+d)) AS prr,
       exp(ln((a/(a+b))/(c/(c+d))) - 1.96*sqrt(1/a - 1/(a+b) + 1/c - 1/(c+d))) AS prr_lo,
       exp(ln((a/(a+b))/(c/(c+d))) + 1.96*sqrt(1/a - 1/(a+b) + 1/c - 1/(c+d))) AS prr_hi,
       (a*d)/(b*c) AS ror,
       exp(ln((a*d)/(b*c)) - 1.96*sqrt(1/a + 1/b + 1/c + 1/d)) AS ror_lo,
       exp(ln((a*d)/(b*c)) + 1.96*sqrt(1/a + 1/b + 1/c + 1/d)) AS ror_hi,
       N * power(greatest(abs(a*d - b*c) - N/2, 0), 2) / ((a+b)*(c+d)*(a+c)*(b+d)) AS chi2_yates,
       log2((a + 0.5) / (expected + 0.5)) AS ic,
       log2((a + 0.5) / (expected + 0.5)) - 3.3*power(a + 0.5, -0.5) - 2*power(a + 0.5, -1.5) AS ic025
FROM cells
WHERE b > 0 AND c > 0;

-- 신호 판정 (계산은 SQL 이 한다. 모델은 이 숫자를 바꾸지 않는다)
CREATE OR REPLACE TABLE sig_signal AS
SELECT *,
       (prr >= 2 AND chi2_yates >= 4 AND a >= 3) AS evans_signal,
       (ror_lo > 1 AND a >= 3)                  AS ror_signal,
       (ic025 > 0)                              AS ic_signal
FROM sig_disproportionality;

------------------------------------------------------------------ 운영 지표
CREATE OR REPLACE TABLE ops_quarter AS
SELECT v.quarter,
       count(*) AS reports,
       count(DISTINCT v.caseid) AS cases,
       sum(CASE WHEN v.i_f_code = 'I' THEN 1 ELSE 0 END) AS initial_reports,
       sum(CASE WHEN v.i_f_code = 'F' THEN 1 ELSE 0 END) AS followups,
       sum(CASE WHEN v.rept_cod = 'EXP' THEN 1 ELSE 0 END) AS expedited,
       sum(CASE WHEN v.rept_cod = 'PER' THEN 1 ELSE 0 END) AS periodic,
       sum(CASE WHEN v.rept_cod = 'DIR' THEN 1 ELSE 0 END) AS direct
FROM core_case_version v GROUP BY v.quarter ORDER BY v.quarter;
