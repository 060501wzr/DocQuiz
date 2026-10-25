import json
from pathlib import Path

from ..extensions import db
from ..models import Question, QuestionBank

SUPPORTED_TYPES = {"single", "multiple", "true_false", "fill_blank", "short_answer"}


def parse_json_file(file_path: str) -> list[dict]:
    """读取 JSON 文件，返回题目列表。"""
    path = Path(file_path)
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("JSON 顶层必须是数组")

    return data


def validate_question(item: dict) -> None:
    """校验单道题是否符合格式。"""
    if not isinstance(item, dict):
        raise ValueError("题目必须是对象")

    qtype = item.get("type")
    if qtype not in SUPPORTED_TYPES:
        raise ValueError(f"不支持的题型：{qtype}")

    if not item.get("stem"):
        raise ValueError("题干不能为空")

    if "answer" not in item:
        raise ValueError("答案不能为空")

    if qtype in {"single", "multiple"}:
        options = item.get("options")
        if not options or not isinstance(options, list):
            raise ValueError("选择题必须有选项")


def import_questions_from_json(file_path: str, bank_name: str = None) -> dict:
    """导入 JSON 题库到数据库，返回统计结果。"""
    raw_list = parse_json_file(file_path)

    if not raw_list:
        raise ValueError("题库为空")

    bank_name = bank_name or Path(file_path).stem

    bank = QuestionBank(
        name=bank_name,
        source_type="json",
        source_file=Path(file_path).name,
        status="success",
    )
    db.session.add(bank)
    db.session.flush()  # 先拿到 bank.id

    success = 0
    failed = 0
    errors = []

    for index, item in enumerate(raw_list):
        try:
            validate_question(item)
            question = Question(
                bank_id=bank.id,
                type=item["type"],
                stem=item["stem"],
                options=item.get("options"),
                answer=item["answer"],
                analysis=item.get("analysis"),
                subject=item.get("subject"),
                order_no=index + 1,
            )
            db.session.add(question)
            success += 1
        except Exception as e:
            failed += 1
            errors.append(f"第 {index + 1} 题：{e}")

    if success == 0:
        db.session.rollback()
        raise ValueError("全部题目导入失败：" + "；".join(errors))

    if failed > 0:
        bank.status = "partial"

    db.session.commit()

    return {
        "bank_id": bank.id,
        "bank_name": bank.name,
        "success": success,
        "failed": failed,
        "errors": errors,
    }

# 在 app/services/parser.py 末尾加上这个函数
def import_questions_from_data(data_list: list, bank_name: str, user_id: int, bank_id: int = None) -> dict:
    if not data_list or not isinstance(data_list, list):
        raise ValueError("JSON 数据格式错误，必须是数组且不能为空")

    if bank_id:
        bank = QuestionBank.query.get_or_404(bank_id)
        # 找到当前题库最大的题号，方便后面追加
        max_order = db.session.query(db.func.max(Question.order_no)).filter_by(bank_id=bank.id).scalar() or 0
    else:
        bank = QuestionBank(name=bank_name, source_type="json", source_file="",user_id=user_id, status="success")
        db.session.add(bank)
        db.session.flush()
        max_order = 0

    success = 0
    for index, item in enumerate(data_list):
        validate_question(item)
        question = Question(
            bank_id=bank.id,
            type=item["type"],
            stem=item["stem"],
            options=item.get("options"),
            answer=item["answer"],
            analysis=item.get("analysis"),
            subject=item.get("subject"),
            order_no=max_order + index + 1,
        )
        db.session.add(question)
        success += 1

    db.session.commit()
    return {"success": success}