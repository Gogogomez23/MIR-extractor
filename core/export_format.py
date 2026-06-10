from datetime import datetime


def render_quick_export_text(questions):
    parts = []
    for q in questions:
        parts.append(f"Enunciado: {q['enunciado']}\n\n")
        parts.append("Opciones:\n")
        for i, opt in enumerate(q["opciones"], 1):
            parts.append(f"    {i}. {opt}\n")
        parts.append(f"\nRC: {q['rc']}\n\n")
        parts.append(
            f"Tema: {q['tema']} | Especialidad: {q['especialidad']} | "
            f"Dificultad: {q['dificultad']} | Año: {q['ano']}\n\n"
        )
        parts.append(f"Explicación:\n{q['explicacion']}\n")
        parts.append("_________________________________________________________________________________\n\n")
    return "".join(parts)


def render_export_header(title, details=None):
    lines = [title, "=" * 80]
    for detail in details or []:
        if detail:
            lines.append(detail)
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 80)
    lines.append("")
    return "\n".join(lines)


def render_export_document(questions, include_header=False, header_title="Export Summary", header_details=None):
    parts = []
    if include_header:
        parts.append(render_export_header(header_title, header_details))
    parts.append(render_quick_export_text(questions))
    return "".join(parts)
