"""Auction arithmetic shared by server-side validation and state responses."""


def team_summary(sales):
    spent = sum(s['price'] for s in sales)
    gk = sum(s['role_group'] == 'goalkeeper' for s in sales)
    out = len(sales) - gk
    budget = 500 - spent
    reserve = max(3 - gk, 0) + max(20 - out, 0)
    def maximum(group):
        after = max(3 - gk - (group == 'goalkeeper'), 0) + max(20 - out - (group == 'outfield'), 0)
        return max(0, budget - after)
    return dict(spent=spent, remaining_budget=budget, goalkeepers=gk, outfield=out,
                mandatory_remaining=reserve,
                minimum_complete=gk >= 3 and out >= 20,
                max_bid_goalkeeper=maximum('goalkeeper'), max_bid_outfield=maximum('outfield'))


def validate_purchase(sales, group, price):
    summary = team_summary(sales)
    if type(price) is not int or not 1 <= price <= 500:
        raise ValueError('Price must be a whole number from 1 to 500 credits.')
    if price > summary[f'max_bid_{group}']:
        raise ValueError(f"Maximum bid is {summary[f'max_bid_{group}']} credits; reserve credits for the minimum squad.")
