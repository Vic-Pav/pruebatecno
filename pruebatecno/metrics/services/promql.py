def build_promql(alert):
  
    from metrics.models import AlertLogic
    logic_obj = AlertLogic.objects.filter(alert=alert).first()
    logic = logic_obj.logic if logic_obj is not None else "AND"
    operator = " and " if logic == "AND" else " or "

    expressions = []

    for c in alert.conditions.all():
        expressions.append(
            f"{c.metric} {c.operator} {c.threshold}"
        )

    return operator.join(expressions)
