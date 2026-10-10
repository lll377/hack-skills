# PATTERN 8 — Coupon, Referral, and Reward Misuse

### The developer's assumption
*"Each coupon code is one-use. The user's account is flagged after the first use and the code is marked consumed."*

In practice: the "one-use" check and the "mark consumed" write are not atomic. Or: the code is tied to an email, but email uniqueness is weakly enforced. Or: deletion of the account resets the flag.

### Where the assumption breaks
- Race condition on the redemption endpoint (covered in Pattern 2 — always race test coupons)
- A coupon is tied to `email` but the same inbox can receive `user+1@gmail.com`, `user+2@gmail.com`, etc. → unlimited new accounts with the same physical email
- Referral bonus is credited before the referee completes the required action (first purchase, first deposit)
- The referral code is validated on the client side only — bypass by removing the validation call
- Cashback/reward is calculated on the gross amount before returns — refund the purchase after receiving the cashback → net positive balance

### Test sequence
```
1. Obtain a coupon/referral code. Apply it. Note:
   - When does the credit appear? (Immediately vs. after event)
   - What event triggers permanence? (Purchase completion? Email confirm?)

2. Race test: see Pattern 2.

3. Sub-addressing test: create 5 accounts with user+1@, user+2@, etc.
   Apply the "new user" coupon to each. Do all succeed?

4. Referral timing test:
   A refers B. B creates account but does NOT complete the required action.
   Check A's account: is referral bonus already credited?
   If yes: A refers 100 fake accounts → unlimited bonus.

5. Refund-after-reward test:
   Purchase product → receive cashback → refund product.
   Is the cashback reversed? If no: cost = 0, reward = positive.

6. Account deletion reset test:
   Apply coupon → delete account → create new account with same email.
   Is the coupon flag reset?
```

### Signal and chain
- **Positive**: multiple successful uses of a should-be-single-use code, or reward without completing the qualifying action
- **Financial quantification**: always compute the maximum extractable value per hour with a scripted loop — this is what the impact statement needs. $0.50 per referral × 1000 fake accounts/hour = $500/hour.
- **Chain**: Reward misuse → if the platform uses the same credit system for purchases, chain to unlimited free purchases (Critical on e-commerce). Referral misuse → if referral bonus is real money, chain to financial drain (High).

### High-value targets
E-commerce with welcome discounts, fintech with referral programs, gaming with invite rewards, crypto exchanges with trading fee rebates, subscription services with trial-then-cancel flows.

---
