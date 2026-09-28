-- Reporter-mix (occp_cod) for exactly the drug-event pairs in api/_data/signals.json.gz.
-- Run against data/derived/faers.duckdb opened read_only. Expects a relation `pairs(drug, pt, a_extract, prr, ror_lo, ic025, evans, ror_sig, ic_sig)`
-- registered by the caller (built from signals.json.gz). All counts are distinct cases (sig_triplet is DISTINCT primaryid, drug, pt).
-- HCP = MD (physician), PH (pharmacist), HP/OT (other health professional), RN (nurse). LW = lawyer, CN = consumer.

-- 1) Background (NULL occp_cod stays in the denominator, as in the pair shares): the disproportionality case universe (every case with a PS/SS drug and a reaction, same N as signals.json.gz)
CREATE OR REPLACE TEMP TABLE bg AS
SELECT count(*)                                              AS n,
       avg(coalesce(occp_cod = 'LW', false)::INT)                        AS lw,
       avg(coalesce(occp_cod = 'CN', false)::INT)                        AS cn,
       avg(coalesce(occp_cod IN ('MD','PH','HP','OT','RN'), false)::INT) AS hcp
FROM core_case WHERE primaryid IN (SELECT primaryid FROM sig_triplet);

-- 2) Pair mix
CREATE OR REPLACE TEMP TABLE pair_mix AS
SELECT t.drug, t.pt, count(*) AS a,
       count(*) FILTER (c.occp_cod = 'LW')                           AS n_lw,
       count(*) FILTER (c.occp_cod = 'CN')                           AS n_cn,
       count(*) FILTER (c.occp_cod IN ('MD','PH','HP','OT','RN'))    AS n_hcp,
       count(*) FILTER (c.occp_cod IS NULL)                          AS n_na
FROM sig_triplet t
JOIN pairs p     ON p.drug = t.drug AND p.pt = t.pt
JOIN core_case c ON c.primaryid = t.primaryid
GROUP BY t.drug, t.pt;

-- 3) Drug-wide mix (every case where the drug is PS/SS), to tell pair-specific litigation from drug-wide litigation
CREATE OR REPLACE TEMP TABLE drug_mix AS
SELECT d.drug, count(*) AS n,
       count(*) FILTER (c.occp_cod = 'LW')                           AS n_lw,
       count(*) FILTER (c.occp_cod = 'CN')                           AS n_cn,
       count(*) FILTER (c.occp_cod IN ('MD','PH','HP','OT','RN'))    AS n_hcp
FROM (SELECT DISTINCT primaryid, drug FROM sig_triplet WHERE drug IN (SELECT DISTINCT drug FROM pairs)) d
JOIN core_case c USING (primaryid)
GROUP BY d.drug;

-- 4) Shares, lifts, Wilson 95% lower bound of the lawyer share, candidate flags
CREATE OR REPLACE TEMP TABLE mix AS
WITH s AS (
  SELECT p.*, m.a, m.n_lw, m.n_cn, m.n_hcp, m.n_na,
         m.n_lw / m.a  AS lw_share, m.n_cn / m.a AS cn_share, m.n_hcp / m.a AS hcp_share,
         dm.n_lw / dm.n AS drug_lw_share, dm.n_cn / dm.n AS drug_cn_share, dm.n AS drug_n,
         bg.lw AS bg_lw, bg.cn AS bg_cn, bg.hcp AS bg_hcp
  FROM pairs p JOIN pair_mix m USING (drug, pt) JOIN drug_mix dm USING (drug), bg
)
SELECT *,
       lw_share / bg_lw                                    AS lw_lift_bg,
       lw_share / nullif(drug_lw_share, 0)                 AS lw_lift_drug,
       cn_share / bg_cn                                    AS cn_lift_bg,
       -- Wilson score lower bound (z = 1.96) of the lawyer share
       (lw_share + 1.9208/a - 1.96*sqrt(lw_share*(1-lw_share)/a + 0.9604/(a*a))) / (1 + 3.8416/a) AS lw_lo,
       -- Proposed lawyer-driven flag: >=20% lawyer, >=5x the FAERS background, >=10 lawyer reports
       (lw_share >= 0.20 AND lw_share >= 5*bg_lw AND n_lw >= 10)            AS flag_lw,
       -- Proposed consumer-dominated flag: >=90% consumer AND >=30 points above the drug's own consumer share, >=20 cases
       -- (relative to the drug, so OTC and patient-support-programme products are not flagged wholesale)
       (a >= 20 AND cn_share >= 0.90 AND cn_share - drug_cn_share >= 0.30)  AS flag_cn
FROM s;
