"""Painel de controlo simples: ativar/desativar a tarefa agendada, escolher
clubes/fontes ativos, e correr o pipeline manualmente."""

import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext

import settings
from config import BASE_DIR, LOG_DIR

TASK_NAME = "NewsAI Pipeline"

CLUB_LABELS = {"fc_porto": "FC Porto", "benfica": "Benfica", "sporting": "Sporting"}
SOURCE_LABELS = {
    "ojogo": "O Jogo",
    "abola": "A Bola",
    "record": "Record",
    "dimarzio": "Gianluca Di Marzio (RSS)",
    "fabrizio_telegram": "Fabrizio Romano (Telegram)",
    "athletic": "The Athletic — David Ornstein",
    "marca": "Marca (liga portuguesa)",
    "lequipe": "L'Équipe (liga portuguesa)",
}


class ControlPanel(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("NewsAI — Painel de Controlo")
        self.geometry("540x640")
        self.resizable(False, False)

        self.settings_data = settings.load()
        self.club_vars = {}
        self.source_vars = {}
        self.running = False

        self._build_task_section()
        self._build_clubs_section()
        self._build_sources_section()
        self._build_run_section()

        self._refresh_task_status()

    # --- Tarefa agendada ---
    def _build_task_section(self):
        frame = ttk.LabelFrame(self, text="Tarefa agendada (a cada 15 min)")
        frame.pack(fill="x", padx=10, pady=8)

        self.task_status_label = ttk.Label(frame, text="A verificar...")
        self.task_status_label.pack(side="left", padx=8, pady=8)

        ttk.Button(frame, text="Desativar", command=self._disable_task).pack(side="right", padx=4, pady=8)
        ttk.Button(frame, text="Ativar", command=self._enable_task).pack(side="right", padx=4, pady=8)

    def _query_task_status(self) -> str:
        try:
            result = subprocess.run(
                ["schtasks", "/Query", "/TN", TASK_NAME, "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return "tarefa não encontrada"
            parts = [p.strip('"') for p in result.stdout.strip().split('","')]
            return parts[-1] if parts else "desconhecido"
        except Exception as e:
            return f"erro ao consultar ({e})"

    def _refresh_task_status(self):
        status = self._query_task_status()
        self.task_status_label.config(text=f"Estado atual: {status}")

    def _enable_task(self):
        subprocess.run(["schtasks", "/Change", "/TN", TASK_NAME, "/ENABLE"], capture_output=True)
        self._refresh_task_status()

    def _disable_task(self):
        subprocess.run(["schtasks", "/Change", "/TN", TASK_NAME, "/DISABLE"], capture_output=True)
        self._refresh_task_status()

    # --- Clubes ---
    def _build_clubs_section(self):
        frame = ttk.LabelFrame(self, text="Clubes ativos")
        frame.pack(fill="x", padx=10, pady=8)
        for club in settings.ALL_CLUBS:
            var = tk.BooleanVar(value=self.settings_data["clubs"].get(club, False))
            self.club_vars[club] = var
            ttk.Checkbutton(
                frame,
                text=CLUB_LABELS.get(club, club),
                variable=var,
                command=self._save_settings,
            ).pack(anchor="w", padx=8, pady=2)

    # --- Fontes ---
    def _build_sources_section(self):
        frame = ttk.LabelFrame(self, text="Fontes ativas")
        frame.pack(fill="x", padx=10, pady=8)
        for source in settings.ALL_SOURCES:
            var = tk.BooleanVar(value=self.settings_data["sources"].get(source, False))
            self.source_vars[source] = var
            ttk.Checkbutton(
                frame,
                text=SOURCE_LABELS.get(source, source),
                variable=var,
                command=self._save_settings,
            ).pack(anchor="w", padx=8, pady=2)

    def _save_settings(self):
        data = {
            "clubs": {club: var.get() for club, var in self.club_vars.items()},
            "sources": {source: var.get() for source, var in self.source_vars.items()},
        }
        settings.save(data)
        self.settings_data = data

    # --- Execução manual ---
    def _build_run_section(self):
        frame = ttk.LabelFrame(self, text="Execução manual")
        frame.pack(fill="both", expand=True, padx=10, pady=8)

        button_row = ttk.Frame(frame)
        button_row.pack(fill="x", padx=8, pady=4)
        self.run_button = ttk.Button(button_row, text="Correr agora", command=self._run_now)
        self.run_button.pack(side="left")
        ttk.Button(button_row, text="Abrir pasta de logs", command=self._open_logs_folder).pack(side="left", padx=8)

        self.output_box = scrolledtext.ScrolledText(frame, height=16, state="disabled", wrap="word")
        self.output_box.pack(fill="both", expand=True, padx=8, pady=8)

    def _append_output(self, text):
        self.output_box.config(state="normal")
        self.output_box.insert("end", text)
        self.output_box.see("end")
        self.output_box.config(state="disabled")

    def _run_now(self):
        if self.running:
            return
        self.running = True
        self.run_button.config(state="disabled", text="A correr...")
        self.output_box.config(state="normal")
        self.output_box.delete("1.0", "end")
        self.output_box.config(state="disabled")

        thread = threading.Thread(target=self._run_pipeline_thread, daemon=True)
        thread.start()

    def _run_pipeline_thread(self):
        try:
            process = subprocess.Popen(
                [sys.executable, str(BASE_DIR / "main.py")],
                cwd=str(BASE_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
            for line in process.stdout:
                self.after(0, self._append_output, line)
            process.wait()
        except Exception as e:
            self.after(0, self._append_output, f"\nErro ao correr o pipeline: {e}\n")
        finally:
            self.after(0, self._on_run_finished)

    def _on_run_finished(self):
        self.running = False
        self.run_button.config(state="normal", text="Correr agora")

    def _open_logs_folder(self):
        subprocess.run(["explorer", str(LOG_DIR)])


if __name__ == "__main__":
    app = ControlPanel()
    app.mainloop()
