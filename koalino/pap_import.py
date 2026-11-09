"""Diagrammdaten des PAP-Editors (pap.mint-checker.de) in der Zwischenablage.

Der PAP-Editor legt beim „In Projekt übernehmen“ neben dem Bild auch die
Diagrammdaten (JSON: ``nodes`` + ``arrows``) unter diesem MIME-Typ in die
Zwischenablage (siehe ``pap_editor.py``). Die frühere Umwandlung nach Mermaid
für den lokalen Code-Generator ist mit dem Ollama-Pfad entfallen.
"""

# MIME-Typ, unter dem der PAP-Editor die Diagrammdaten in die Zwischenablage legt.
PAP_MIME = "application/x-nit-pap+json"
