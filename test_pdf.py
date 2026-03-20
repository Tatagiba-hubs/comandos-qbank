from pdf_generator import generate_simulado_pdf

questions = [
    {
        "subject": "Matematica",
        "exam_origin": "EsPCEx",
        "year": "2023",
        "difficulty": "Medio",
        "question_text": "Resolva a equacao linear simple:\n2x + 4 = 10",
        "options": {"A": "1", "B": "2", "C": "3", "D": "4", "E": "5"},
        "correct_answer_letter": "C"
    },
    {
        "subject": "Fisica",
        "exam_origin": "EsPCEx",
        "year": "2022",
        "difficulty": "Dificil",
        "question_text": "Um bloco de 10kg cai de 5m. Qual a energia potencial?",
        "options": {"A": "100J", "B": "200J", "C": "300J", "D": "400J", "E": "500J"},
        "correct_answer_letter": "E"
    }
]

try:
    generate_simulado_pdf(questions, "teste_simulado.pdf")
    print("SUCCESS")
except Exception as e:
    import traceback
    traceback.print_exc()
