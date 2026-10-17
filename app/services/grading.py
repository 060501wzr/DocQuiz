def grade_question(question, user_answer):
    """
    返回：
    True  -> 客观题答对
    False -> 客观题答错
    None  -> 主观题，不自动判分
    """
    qtype = question.type
    correct = question.answer

    if qtype == "single":
        return user_answer == correct

    if qtype == "multiple":
        if not user_answer:
            return False
        return set(user_answer) == set(correct)

    if qtype == "true_false":
        user_bool = user_answer == "true"
        return user_bool == correct

    # fill_blank / short_answer
    return None