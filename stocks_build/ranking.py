"""Cross-row ranking logic for the HK stocks dashboard."""


def competition_rank(sorted_items):
    ranks = {}
    for pos0, (idx, value) in enumerate(sorted_items):
        if pos0 == 0:
            ranks[idx] = 1
        elif value == sorted_items[pos0 - 1][1]:
            ranks[idx] = ranks[sorted_items[pos0 - 1][0]]
        else:
            ranks[idx] = pos0 + 1
    return ranks


def compute_rankings(phase1_list):
    count = len(phase1_list)
    financial = [i for i, data in enumerate(phase1_list) if data["is_jinrong"]]
    non_financial = [i for i, data in enumerate(phase1_list) if not data["is_jinrong"]]

    undervalue = [None] * count
    financial_pe = [(i, phase1_list[i]["pe_ttm"]) for i in financial if phase1_list[i]["pe_ttm"] is not None and phase1_list[i]["pe_ttm"] > 0]
    financial_pe.sort(key=lambda item: item[1])
    ranks = competition_rank(financial_pe)
    for idx in financial:
        pe_ttm = phase1_list[idx]["pe_ttm"]
        if pe_ttm is not None and pe_ttm > 0:
            undervalue[idx] = ranks.get(idx)

    non_financial_yield = [
        (i, phase1_list[i]["shareholder_yield"])
        for i in non_financial
        if phase1_list[i]["shareholder_yield"] is not None and phase1_list[i]["shareholder_yield"] > 0
    ]
    non_financial_yield.sort(key=lambda item: item[1], reverse=True)
    ranks = competition_rank(non_financial_yield)
    for idx in non_financial:
        shareholder_yield = phase1_list[idx]["shareholder_yield"]
        if shareholder_yield is not None and shareholder_yield > 0:
            undervalue[idx] = ranks.get(idx)

    growth = [None] * count
    for queue in (financial, non_financial):
        items = [(i, 0.0 if phase1_list[i]["ttm_yoy"] is None else phase1_list[i]["ttm_yoy"]) for i in queue]
        items.sort(key=lambda item: item[1], reverse=True)
        ranks = competition_rank(items)
        for idx in queue:
            growth[idx] = ranks.get(idx)

    quality = [None] * count
    financial_quality = [(i, phase1_list[i]["ttmroe"]) for i in financial if phase1_list[i]["ttmroe"] is not None]
    financial_quality.sort(key=lambda item: item[1], reverse=True)
    ranks = competition_rank(financial_quality)
    for idx in financial:
        if phase1_list[idx]["ttmroe"] is not None:
            quality[idx] = ranks.get(idx)

    non_financial_quality = [(i, phase1_list[i]["ttmroic"]) for i in non_financial if phase1_list[i]["ttmroic"] is not None]
    non_financial_quality.sort(key=lambda item: item[1], reverse=True)
    ranks = competition_rank(non_financial_quality)
    for idx in non_financial:
        if phase1_list[idx]["ttmroic"] is not None:
            quality[idx] = ranks.get(idx)

    def calc_return_dist(queue_indices):
        queue_size = len(queue_indices)
        positive = [
            (i, phase1_list[i]["return_ratio"])
            for i in queue_indices
            if phase1_list[i]["return_ratio"] is not None and phase1_list[i]["return_ratio"] > 0
        ]
        positive.sort(key=lambda item: item[1], reverse=True)
        ranks = competition_rank(positive)
        result = {}
        for idx in queue_indices:
            return_ratio = phase1_list[idx]["return_ratio"]
            result[idx] = ranks.get(idx, queue_size) if return_ratio is not None and return_ratio > 0 else queue_size
        return result

    return_dist = [None] * count
    financial_return = calc_return_dist(financial)
    non_financial_return = calc_return_dist(non_financial)
    for idx in financial:
        return_dist[idx] = financial_return.get(idx)
    for idx in non_financial:
        return_dist[idx] = non_financial_return.get(idx)

    composite = [None] * count
    for idx in range(count):
        pieces = (undervalue[idx], growth[idx], quality[idx], return_dist[idx])
        if None not in pieces:
            composite[idx] = round(pieces[0] * 0.4 + pieces[1] * 0.2 + pieces[2] * 0.2 + pieces[3] * 0.2, 1)

    composite_rank = [None] * count
    for queue in (financial, non_financial):
        items = [(i, composite[i]) for i in queue if composite[i] is not None]
        items.sort(key=lambda item: item[1])
        ranks = competition_rank(items)
        for idx in queue:
            if composite[idx] is not None:
                composite_rank[idx] = ranks.get(idx)

    def rank_str(value):
        return "--" if value is None else str(int(value))

    def composite_str(value):
        return "--" if value is None else str(value)

    return [
        [
            rank_str(undervalue[idx]),
            rank_str(growth[idx]),
            rank_str(quality[idx]),
            rank_str(return_dist[idx]),
            composite_str(composite[idx]),
            rank_str(composite_rank[idx]),
        ]
        for idx in range(count)
    ]

