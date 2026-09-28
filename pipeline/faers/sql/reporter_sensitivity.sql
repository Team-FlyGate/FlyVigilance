-- Sensitivity check for lawyer-flagged pairs: recompute the same disproportionality (model.sql formulas)
-- after removing lawyer-reported cases from the whole universe (N, n_drug, n_pt, a all shrink together).
-- Needs `mix` (from reporter_mix.sql, or the saved pair_reporter_mix.parquet) in scope.
CREATE OR REPLACE TEMP TABLE flagged AS SELECT drug, pt, a, n_lw, prr, ror_lo, ic025 FROM mix WHERE flag_lw OR flag_cn;

CREATE OR REPLACE TEMP TABLE n0 AS
SELECT count(*)::DOUBLE AS N FROM core_case
WHERE primaryid IN (SELECT primaryid FROM sig_triplet) AND occp_cod IS DISTINCT FROM 'LW';

CREATE OR REPLACE TEMP TABLE drug0 AS
SELECT t.drug, count(DISTINCT t.primaryid)::DOUBLE AS n_drug
FROM sig_triplet t JOIN core_case c USING (primaryid)
WHERE t.drug IN (SELECT drug FROM flagged) AND c.occp_cod IS DISTINCT FROM 'LW'
GROUP BY t.drug;

CREATE OR REPLACE TEMP TABLE pt0 AS
SELECT t.pt, count(DISTINCT t.primaryid)::DOUBLE AS n_pt
FROM sig_triplet t JOIN core_case c USING (primaryid)
WHERE t.pt IN (SELECT pt FROM flagged) AND c.occp_cod IS DISTINCT FROM 'LW'
GROUP BY t.pt;

CREATE OR REPLACE TEMP TABLE sens AS
WITH cells AS (
  SELECT f.drug, f.pt, f.a AS a_all, f.prr AS prr_all, f.ror_lo AS ror_lo_all, f.ic025 AS ic025_all,
         (f.a - f.n_lw)::DOUBLE AS a, d.n_drug - (f.a - f.n_lw) AS b, p.n_pt - (f.a - f.n_lw) AS c,
         n0.N - d.n_drug - p.n_pt + (f.a - f.n_lw) AS d, d.n_drug * p.n_pt / n0.N AS expected, n0.N
  FROM flagged f JOIN drug0 d USING (drug) JOIN pt0 p USING (pt), n0
)
SELECT drug, pt, a_all, prr_all, ror_lo_all, ic025_all, a::BIGINT AS a_nolw,
       CASE WHEN a > 0 AND b > 0 AND c > 0 THEN (a/(a+b)) / (c/(c+d)) END AS prr_nolw,
       CASE WHEN a > 0 AND b > 0 AND c > 0 THEN exp(ln((a*d)/(b*c)) - 1.96*sqrt(1/a + 1/b + 1/c + 1/d)) END AS ror_lo_nolw,
       log2((a + 0.5) / (expected + 0.5)) - 3.3*power(a + 0.5, -0.5) - 2*power(a + 0.5, -1.5) AS ic025_nolw,
       CASE WHEN a > 0 AND b > 0 AND c > 0 THEN N * power(greatest(abs(a*d - b*c) - N/2, 0), 2) / ((a+b)*(c+d)*(a+c)*(b+d)) END AS chi2_nolw
FROM cells;

-- HCP-only variant: keep only cases reported by MD, PH, HP, OT, RN (drops LW, CN and unknown)
CREATE OR REPLACE TEMP TABLE hcp_pair AS
SELECT t.drug, t.pt, count(*)::DOUBLE AS a
FROM sig_triplet t JOIN flagged f ON f.drug = t.drug AND f.pt = t.pt JOIN core_case c ON c.primaryid = t.primaryid
WHERE c.occp_cod IN ('MD','PH','HP','OT','RN') GROUP BY 1, 2;
CREATE OR REPLACE TEMP TABLE hcp_n AS
SELECT count(*)::DOUBLE AS N FROM core_case
WHERE primaryid IN (SELECT primaryid FROM sig_triplet) AND occp_cod IN ('MD','PH','HP','OT','RN');
CREATE OR REPLACE TEMP TABLE hcp_drug AS
SELECT t.drug, count(DISTINCT t.primaryid)::DOUBLE AS n_drug FROM sig_triplet t JOIN core_case c USING (primaryid)
WHERE t.drug IN (SELECT drug FROM flagged) AND c.occp_cod IN ('MD','PH','HP','OT','RN') GROUP BY 1;
CREATE OR REPLACE TEMP TABLE hcp_pt AS
SELECT t.pt, count(DISTINCT t.primaryid)::DOUBLE AS n_pt FROM sig_triplet t JOIN core_case c USING (primaryid)
WHERE t.pt IN (SELECT pt FROM flagged) AND c.occp_cod IN ('MD','PH','HP','OT','RN') GROUP BY 1;
CREATE OR REPLACE TEMP TABLE sens_hcp AS
WITH cells AS (
  SELECT f.drug, f.pt, coalesce(h.a, 0) AS a, d.n_drug - coalesce(h.a, 0) AS b, p.n_pt - coalesce(h.a, 0) AS c,
         n.N - d.n_drug - p.n_pt + coalesce(h.a, 0) AS d, d.n_drug * p.n_pt / n.N AS expected, n.N
  FROM flagged f LEFT JOIN hcp_pair h USING (drug, pt) JOIN hcp_drug d USING (drug) JOIN hcp_pt p USING (pt), hcp_n n
)
SELECT drug, pt, a::BIGINT AS a_hcp,
       CASE WHEN a > 0 AND b > 0 AND c > 0 THEN (a/(a+b)) / (c/(c+d)) END AS prr_hcp,
       CASE WHEN a > 0 AND b > 0 AND c > 0 THEN exp(ln((a*d)/(b*c)) - 1.96*sqrt(1/a + 1/b + 1/c + 1/d)) END AS ror_lo_hcp,
       log2((a + 0.5) / (expected + 0.5)) - 3.3*power(a + 0.5, -0.5) - 2*power(a + 0.5, -1.5) AS ic025_hcp,
       CASE WHEN a > 0 AND b > 0 AND c > 0 THEN N * power(greatest(abs(a*d - b*c) - N/2, 0), 2) / ((a+b)*(c+d)*(a+c)*(b+d)) END AS chi2_hcp
FROM cells;
