"""Auction arithmetic shared by server-side validation and state responses."""


def team_summary(sales):
    spent = sum(s['price'] for s in sales)
    gk = sum(s['role_group'] == 'goalkeeper' for s in sales)
    out = len(sales) - gk
    budget = 500 - spent
    reserve = max(5 - gk, 0) + max(20 - out, 0)
    def maximum(group):
        if (gk >= 5 if group == 'goalkeeper' else out >= 25):
            return 0
        after = max(5 - gk - (group == 'goalkeeper'), 0) + max(20 - out - (group == 'outfield'), 0)
        return max(0, budget - after)
    return dict(spent=spent, remaining_budget=budget, goalkeepers=gk, outfield=out,
                mandatory_remaining=reserve, optional_remaining=max(25 - max(out, 20), 0),
                minimum_complete=gk == 5 and out >= 20,
                complete=gk == 5 and out == 25,
                max_bid_goalkeeper=maximum('goalkeeper'), max_bid_outfield=maximum('outfield'))


def validate_purchase(sales, group, price):
    summary = team_summary(sales)
    if type(price) is not int or not 1 <= price <= 500:
        raise ValueError('Price must be a whole number from 1 to 500 credits.')
    if (summary['goalkeepers'] >= 5 if group == 'goalkeeper' else summary['outfield'] >= 25):
        raise ValueError(f'No {group} slots left.')
    if price > summary[f'max_bid_{group}']:
        raise ValueError(f"Maximum bid is {summary[f'max_bid_{group}']} credits; reserve credits for the minimum squad.")
