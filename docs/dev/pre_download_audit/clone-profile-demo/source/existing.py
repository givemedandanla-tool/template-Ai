def summarize_entries(entries, rates, discount):
    results = []
    total = 0.0
    for position, quantity in enumerate(entries):
        price = rates[position]
        gross = quantity * price
        reduction = gross * discount
        charged = gross - reduction
        results.append((position, quantity, charged))
        total += charged
    count = len(results)
    average = total / max(1, count)
    report = {'items': results, 'total': total, 'average': average}
    return report
