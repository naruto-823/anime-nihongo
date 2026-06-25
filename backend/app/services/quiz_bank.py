from app.services.conjugation import conjugate


def _distractors(target, pool, key, n=3):
    """从 pool 取 n 个与 target[key] 不同的值,去重。"""
    seen = {key(target)}
    out = []
    for item in pool:
        v = key(item)
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out[:n]


def _assemble(correct, distractors, rng):
    opts = [correct, *distractors]
    rng.shuffle(opts)
    return opts


def _ensure_four(correct, distractors, pool, key, rng):
    """确保 distractors 凑足 3 个不同值(与 correct 不同,互相不重复)。
    充足池下必然达成;不足时尽力补齐。"""
    need = 3 - len(distractors)
    if need <= 0:
        return distractors
    seen = {correct, *distractors}
    for item in pool:
        if need <= 0:
            break
        v = key(item)
        if v not in seen:
            seen.add(v)
            distractors.append(v)
            need -= 1
    return distractors


def vocab_meaning_q(target, pool, rng) -> dict:
    others = [v for v in pool if v.id != target.id]
    rng.shuffle(others)
    distractors = _distractors(target, others, key=lambda v: v.meaning_zh)
    if len(distractors) < 3:
        distractors = _ensure_four(target.meaning_zh, distractors, others,
                                   key=lambda v: v.meaning_zh, rng=rng)
    options = _assemble(target.meaning_zh, distractors, rng)
    return {
        "id": f"v{target.id}-meaning",
        "type": "meaning",
        "prompt": f"{target.headword}（{target.reading}）",
        "hint": "选择正确的中文释义",
        "options": options,
        "answer": target.meaning_zh,
        "item": {"kind": "vocab", "id": target.id},
    }


def vocab_reading_q(target, pool, rng):
    if target.headword == target.reading:   # 纯假名,无读音可考
        return None
    others = [v for v in pool if v.id != target.id and v.reading != target.reading]
    rng.shuffle(others)
    distractors = _distractors(target, others, key=lambda v: v.reading)
    if len(distractors) < 3:
        return None
    options = _assemble(target.reading, distractors, rng)
    return {
        "id": f"v{target.id}-reading",
        "type": "reading",
        "prompt": target.headword,
        "hint": "选择正确的假名读音",
        "options": options,
        "answer": target.reading,
        "item": {"kind": "vocab", "id": target.id},
    }


def vocab_conjugation_q(target, rng):
    table = conjugate(target.headword, target.reading, target.pos or "")
    if table is None:
        return None
    forms = [f for f in table["forms"] if f["key"] != "dictionary"]
    # 表层去重,确保有 ≥4 个互不相同的选项
    uniq = []
    seen = set()
    for f in forms:
        if f["surface"] not in seen:
            seen.add(f["surface"])
            uniq.append(f)
    if len(uniq) < 4:
        return None
    rng.shuffle(uniq)
    answer_form = uniq[0]
    distractors = [f["surface"] for f in uniq[1:4]]
    options = _assemble(answer_form["surface"], distractors, rng)
    return {
        "id": f"v{target.id}-conj-{answer_form['key']}",
        "type": "conjugation",
        "prompt": target.headword,
        "hint": f"请选出「{answer_form['label']}」",
        "options": options,
        "answer": answer_form["surface"],
        "item": {"kind": "vocab", "id": target.id},
    }


def grammar_meaning_q(target, pool, rng):
    others = [g for g in pool if g.id != target.id and g.explanation != target.explanation]
    rng.shuffle(others)
    distractors = _distractors(target, others, key=lambda g: g.explanation)
    if len(distractors) < 3:
        full_others = [g for g in pool if g.id != target.id]
        rng.shuffle(full_others)
        distractors = _ensure_four(target.explanation, distractors, full_others,
                                   key=lambda g: g.explanation, rng=rng)
    options = _assemble(target.explanation, distractors, rng)
    return {
        "id": f"g{target.id}-grammar",
        "type": "grammar",
        "prompt": target.name,
        "hint": "选择正确的中文含义",
        "options": options,
        "answer": target.explanation,
        "item": {"kind": "grammar", "id": target.id},
    }


def make_vocab_question(target, pool, rng):
    builders = [lambda: vocab_conjugation_q(target, rng),
                lambda: vocab_reading_q(target, pool, rng)]
    rng.shuffle(builders)
    for build in builders:
        q = build()
        if q is not None and rng.random() < 0.7:   # 偏向变化,但保证有回退
            return q
    return vocab_meaning_q(target, pool, rng)


def make_grammar_question(target, pool, rng):
    return grammar_meaning_q(target, pool, rng)
