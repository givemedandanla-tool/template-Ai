def compute_summary(records, prices, allowance):
    output = []
    aggregate = 0.0
    for offset, amount in enumerate(records):
        price = prices[offset]
        subaggregate = amount * price
        rebate = subaggregate * allowance
        net = subaggregate - rebate
        output.append((offset, amount, net))
        aggregate += net
    size = len(output)
    mean = aggregate / max(1, size)
    summary = {'items': output, 'total': aggregate, 'average': mean}
    return summary
