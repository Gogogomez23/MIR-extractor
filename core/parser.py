import re
import pdfplumber


def clean_text_hyphens(raw_text):
    return re.sub(r'-\s*([a-zñáéíóú])', r'\1', raw_text)


def parse_pdf_stream(text, default_specialty, default_tema):
    extracted_data = []
    raw_chunks = re.split(r'(?:\n|^)(MIR\s+\d{4})(?:\n|$)', text)
    start_index = 1 if len(raw_chunks) > 1 and re.match(r'MIR\s+\d{4}', raw_chunks[1].strip()) else 0

    iterator_range = []
    if start_index == 0:
        iterator_range.append(("", text))
    else:
        for idx in range(1, len(raw_chunks), 2):
            iterator_range.append((raw_chunks[idx], raw_chunks[idx + 1] if (idx + 1) < len(raw_chunks) else ""))

    for year_tag, body in iterator_range:
        year_match = re.search(r'\d{4}', year_tag)
        year = year_match.group(0) if year_match else "2024"

        num_match = re.search(r'^\s*(\d+)\.', body, re.MULTILINE)
        if not num_match:
            continue
        q_num = num_match.group(1)

        body_cleaned = re.sub(r'Preguntas MIR.*|Libro Gordo.*|Tema\s+\d+.*', '', body)
        lines = body_cleaned.split('\n')

        enunciado_parts = []
        options_dict = {}
        explanation_parts = []
        rc = "Unknown"
        current_target = "E"
        highest_option_seen = 0

        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue

            opt_match = re.match(r'^([1-5])\.\s(.*)', line_str)
            resp_match = re.search(r'Respuesta:\s*(\d)', line_str)

            if resp_match:
                rc = resp_match.group(1)
                current_target = "EX"
                remain = re.sub(r'Respuesta:\s*\d', '', line_str).strip()
                if remain:
                    explanation_parts.append(remain)
                continue
            elif opt_match:
                opt_num = int(opt_match.group(1))
                current_target = opt_num
                highest_option_seen = max(highest_option_seen, opt_num)
                options_dict[opt_num] = [opt_match.group(2)]
                continue

            if isinstance(current_target, int) and current_target >= 4 and not opt_match:
                is_commentary_keyword = any(line_str.lower().startswith(w) for w in [
                    "pregunta", "caso", "hombre", "paciente", "mujer", "se trata", "esta", "es una", "ante la"
                ])
                has_completed_option_sentence = False
                if current_target in options_dict and options_dict[current_target]:
                    previous_chunk = options_dict[current_target][-1].strip()
                    if previous_chunk.endswith('.') and not re.search(r'\b(ej|vol|cm|ca|co)\.$',
                                                                      previous_chunk.lower()):
                        has_completed_option_sentence = True

                if is_commentary_keyword or (len(line_str) > 40 and has_completed_option_sentence):
                    current_target = "EX"

            if current_target == "E":
                if line_str != f"{q_num}.":
                    enunciado_parts.append(line_str)
            elif isinstance(current_target, int):
                options_dict[current_target].append(line_str)
            elif current_target == "EX":
                explanation_parts.append(line_str)

        options_final = []
        total_slots = max(4, highest_option_seen)
        for o_idx in range(1, total_slots + 1):
            if o_idx in options_dict:
                options_final.append(" ".join(options_dict[o_idx]))
            else:
                options_final.append("")

        full_enunciado = " ".join(enunciado_parts).strip()
        if len(full_enunciado) < 15 and "imagen" not in full_enunciado.lower():
            continue

        full_explicacion = " ".join(explanation_parts).strip()

        status_icon = "🟢 OK"
        status_details = "Correctly parsed."
        if rc == "Unknown" or not full_explicacion:
            status_icon = "🟡 REVIEW"
            status_details = "Missing explanation text or Answer index."
        if len(options_final) < 4 or any(len(opt) < 3 for opt in options_final):
            status_icon = "🔴 ERROR"
            status_details = "Options structure is corrupted."

        extracted_data.append({
            "num": q_num, "ano": year, "enunciado": full_enunciado,
            "opciones": options_final, "rc": rc, "tema": default_tema,
            "especialidad": default_specialty, "dificultad": "Media",
            "explicacion": full_explicacion, "status": status_icon,
            "status_msg": status_details
        })
    return extracted_data