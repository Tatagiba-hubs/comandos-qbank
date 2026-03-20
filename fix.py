with open("app.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

in_tab = False
for i, line in enumerate(lines):
    if line.strip() == "with tab1:" and "if user_info" in lines[i-1]:
        in_tab = True
        continue
    if in_tab:
        if line.startswith("# ── Tab"):
            in_tab = False
        elif line.strip() != "":
            lines[i] = "    " + line

with open("app.py", "w", encoding="utf-8") as f:
    f.writelines(lines)
