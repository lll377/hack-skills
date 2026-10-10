# PATTERN 5 — Price and Quantity Manipulation

### The developer's assumption
*"The price is set server-side from our catalog. The client only sends the quantity, and we validate it's positive."*

In practice: the price *or* a discount factor is trusted from the client. Or: the quantity validation happens in the payment service but not the inventory service. Or: the validation is correct for integers but not for floats.

### Where the assumption breaks
- Price passed in the cart request body (`unit_price: 0.01`) and the server uses it
- Negative quantity in one line item offsets another (`qty: -1` of a $100 item + `qty: 1` of a $100 item → $0)
- Floating point: quantity `0.9999999999` passes the "must be ≤ 1" check but rounds up to 1 on the debit side
- Integer overflow: quantity `2147483648` overflows to a negative, resulting in a credit
- Coupon applied before tax calculation, but tax is calculated on the discounted price — compounding discount vs. intended order of operations

### Test sequence
```
1. Add a product to cart. Intercept the checkout request.
   Identify which parameters carry: price, quantity, discount, tax.

2. Modify price directly: change unit_price from 99.99 to 0.01.
   Does the order total reflect the modified price?

3. Modify quantity to negative: qty=-1 (add a second item at qty=1 to see net effect).

4. Try non-integer quantities: 0.001, 0.9999999, 1.0000001.

5. Apply coupon codes: does the endpoint validate the price again after applying the coupon?
   Try modifying the post-coupon price.

6. Test the sequence: apply coupon BEFORE vs AFTER setting quantity.
   Some discounts are calculated on the quantity at the time of application,
   then the quantity can be increased without recalculating.
```

### Signal and chain
- **Positive**: order placed at a price lower than catalog, or quantity mismatch between what was charged and what was granted
- **Reproducibility requirement**: must show monetary impact — a $0.01 order for a $100 product is more impactful evidence than a theoretical proof
- **Chain**: Price manipulation → direct financial loss to the platform (Critical on e-commerce). Quantity manipulation on digital goods → license/seat inflation (High on SaaS).

### High-value targets
E-commerce, SaaS seat/license purchasing, digital good purchase flows (credits, tokens), marketplace platforms, any system with a promotional pricing model.

---
