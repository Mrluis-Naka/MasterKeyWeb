"""
Statistical power analysis for the conditional-uniformity paper.
Fills the gap in Section 2.7 (previously stated with no numbers).

Two tests need a declared power:
  (A) The pre-registered confirmatory test (Section 3.3): one-tailed z-test on the
      proportion of the character '2' at position 7. n = 17,970, H0: p = 1/58.
  (B) The character-frequency chi-square battery (Section 3.2): 58
      categories, df = 57, over the study's various n's.
"""
import numpy as np
from scipy import stats

P0 = 1/58  # Base58 uniformity
ALPHA_1T = 0.05
ALPHA_2T = 0.05


def mde_proportion(n, p0=P0, alpha=ALPHA_1T, power=0.80, one_tailed=True):
    """Minimum detectable effect (MDE) for a one-proportion test.
    Solved numerically, without approximating the SE under H1 by the SE under H0."""
    z_a = stats.norm.isf(alpha) if one_tailed else stats.norm.isf(alpha/2)
    z_b = stats.norm.isf(1-power)
    se0 = np.sqrt(p0*(1-p0)/n)

    # classic-approximation initial guess, then refined by iteration
    p1 = p0 + (z_a + z_b)*se0
    for _ in range(200):
        se1 = np.sqrt(p1*(1-p1)/n)
        p1_new = p0 + z_a*se0 + z_b*se1
        if abs(p1_new - p1) < 1e-15:
            break
        p1 = p1_new
    return p1


def power_proportion(n, p1, p0=P0, alpha=ALPHA_1T, one_tailed=True):
    """Power to detect the alternative proportion p1."""
    z_a = stats.norm.isf(alpha) if one_tailed else stats.norm.isf(alpha/2)
    se0 = np.sqrt(p0*(1-p0)/n)
    se1 = np.sqrt(p1*(1-p1)/n)
    return float(stats.norm.sf((p0 + z_a*se0 - p1)/se1))


def power_chi2(n, w, df=57, alpha=0.05):
    """Power of the goodness-of-fit chi-square test. w = Cohen's effect size."""
    crit = stats.chi2.isf(alpha, df)
    ncp = n * w**2
    return float(stats.ncx2.sf(crit, df, ncp))


def w_for_power(n, df=57, alpha=0.05, power=0.80):
    """Smallest Cohen's w detectable at the requested power."""
    lo, hi = 1e-6, 1.0
    for _ in range(200):
        mid = (lo+hi)/2
        if power_chi2(n, mid, df, alpha) < power:
            lo = mid
        else:
            hi = mid
    return (lo+hi)/2


def w_of_one_character(delta_rel, k=58):
    """Cohen's w when ONE character deviates by delta_rel (relative) and the other
    (k-1) absorb the excess equally."""
    p0 = 1/k
    p_target = p0*(1+delta_rel)
    p_rest = (1 - p_target)/(k-1)
    w2 = (p_target-p0)**2/p0 + (k-1)*((p_rest-p0)**2/p0)
    return np.sqrt(w2)


print("="*78)
print("(A) PRE-REGISTERED CONFIRMATORY TEST -- Section 3.3")
print("="*78)
n_conf = 17970
print(f"n (confirmation set) = {n_conf:,}")
print(f"H0: p = 1/58 = {P0:.7f}")
print(f"one-tailed test, alpha = {ALPHA_1T}\n")

print(f"{'power':>8} | {'detectable p1':>14} | {'relative excess':>17} | {'expected occurrences':>22}")
print("-"*72)
for pw in (0.50, 0.80, 0.90, 0.95):
    p1 = mde_proportion(n_conf, power=pw)
    rel = (p1-P0)/P0
    print(f"{pw:>8.0%} | {p1:>14.6f} | {rel:>16.1%} | {p1*n_conf:>22.1f}")

print(f"\n(under H0, {P0*n_conf:.1f} occurrences are expected; 267 were observed)")

print("\nRetrospective power for fixed-size effects:")
print(f"{'relative excess':>17} | {'power':>8}")
print("-"*30)
for rel in (0.05, 0.10, 0.1382, 0.15, 0.20, 0.25, 0.30):
    p1 = P0*(1+rel)
    print(f"{rel:>16.1%} | {power_proportion(n_conf, p1):>8.1%}")

print("\n" + "="*78)
print("(B) CHARACTER-FREQUENCY CHI-SQUARE -- Section 3.2")
print("="*78)
for label, n in (("generating set (position 7)", 21753),
                  ("confirmation set", 17970),
                  ("main study", 50995),
                  ("accumulated corpus", 504183)):
    w80 = w_for_power(n)
    # translate the detectable w back into a single-character deviation
    lo, hi = 1e-6, 5.0
    for _ in range(200):
        mid = (lo+hi)/2
        if w_of_one_character(mid) < w80:
            lo = mid
        else:
            hi = mid
    rel_equiv = (lo+hi)/2
    print(f"{label:>30} | n = {n:>7,} | w(80% power) = {w80:.5f} | "
          f"equivalent to 1 character deviating by {rel_equiv:>6.1%}")

print("\nChi-square power (df=57) against a single-character deviation:")
print(f"{'n':>10} | " + " | ".join(f"{r:>7.0%}" for r in (0.10, 0.15, 0.20, 0.30, 0.50)))
print("-"*66)
for n in (17970, 21753, 50995, 504183):
    row = [f"{power_chi2(n, w_of_one_character(r)):>7.1%}" for r in (0.10, 0.15, 0.20, 0.30, 0.50)]
    print(f"{n:>10,} | " + " | ".join(row))
