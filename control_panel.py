"""Painel de controlo simples: ativar/desativar as tarefas agendadas, escolher
clubes/fontes ativos, e correr os scripts manualmente."""

import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext

import settings
from config import BASE_DIR, LOG_DIR

CLOUD_TASK_NAME = "NewsAI Pipeline"
OJOGO_TASK_NAME = "NewsAI Ojogo Local"

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
    "footmercato": "Foot Mercato (live transferências)",
    "gazzetta": "Gazzetta dello Sport (live mercato)",
}


class ControlPanel(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("NewsAI — Painel de Controlo")
        self.geometry("560x760")
        self.resizable(False, False)

        self.settings_data = settings.load()
        self.club_vars = {}
        self.source_vars = {}
        self.running = False
        self.task_status_labels = {}

        self._build_task_section(
            CLOUD_TASK_NAME,
            "Tarefa agendada — pipeline completo na nuvem já corre via GitHub Actions; "
            "esta tarefa local está desativada por defeito para não duplicar envios.",
        )
        self._build_task_section(
            OJOGO_TASK_NAME,
            "Tarefa agendada — só o ojogo.pt (a cada 15 min), porque este site bloqueia "
            "pedidos vindos da nuvem. Corre neste PC e partilha os dados com a nuvem.",
        )
        self._build_clubs_section()
        self._build_sources_section()
        self._build_run_section()

        self._refresh_all_task_statuses()

    # --- Tarefas agendadas ---
    def _build_task_section(self, task_name, description):
        frame = ttk.LabelFrame(self, text=task_name)
        frame.pack(fill="x", padx=10, pady=6)

        ttk.Label(frame, text=description, wraplength=460, justify="left").pack(
            anchor="w", padx=8, pady=(6, 2)
        )

        row = ttk.Frame(frame)
        row.pack(fill="x", padx=8, pady=(0, 8))
        label = ttk.Label(row, text="A verificar...")
        label.pack(side="left")
        self.task_status_labels[task_name] = label

        ttk.Button(row, text="Desativar", command=lambda: self._disable_task(task_name)).pack(
            side="right", padx=4
        )
        ttk.Button(row, text="Ativar", command=lambda: self._enable_task(task_name)).pack(
            side="right", padx=4
        )

    def _query_task_status(self, task_name) -> str:
        try:
            result = subprocess.run(
                ["schtasks", "/Query", "/TN", task_name, "/FO", "CSV", "/NH"],
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

    def _refresh_all_task_statuses(self):
        for task_name, label in self.task_status_labels.items():
            status = self._query_task_status(task_name)
            label.config(text=f"Estado atual: {status}")

    def _enable_task(self, task_name):
        subprocess.run(["schtasks", "/Change", "/TN", task_name, "/ENABLE"], capture_output=True)
        self._refresh_all_task_statuses()

    def _disable_task(self, task_name):
        subprocess.run(["schtasks", "/Change", "/TN", task_name, "/DISABLE"], capture_output=True)
        self._refresh_all_task_statuses()

    # --- Clubes ---
    def _build_clubs_section(self):
        frame = ttk.LabelFrame(self, text="Clubes ativos")
        frame.pack(fill="x", padx=10, pady=6)
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
        frame.pack(fill="x", padx=10, pady=6)
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
        frame.pack(fill="both", expand=True, padx=10, pady=6)

        button_row = ttk.Frame(frame)
        button_row.pack(fill="x", padx=8, pady=4)
        self.run_pipeline_button = ttk.Button(
            button_row, text="Correr pipeline completo", command=lambda: self._run_now("main.py")
        )
        self.run_pipeline_button.pack(side="left")
        self.run_ojogo_button = ttk.Button(
            button_row, text="Correr só ojogo.pt", command=lambda: self._run_now("run_ojogo_local.py")
        )
        self.run_ojogo_button.pack(side="left", padx=8)
        ttk.Button(button_row, text="Abrir pasta de logs", command=self._open_logs_folder).pack(
            side="left", padx=8
        )

        self.output_box = scrolledtext.ScrolledText(frame, height=16, state="disabled", wrap="word")
        self.output_box.pack(fill="both", expand=True, padx=8, pady=8)

    def _append_output(self, text):
        self.output_box.config(state="normal")
        self.output_box.insert("end", text)
        self.output_box.see("end")
        self.output_box.config(state="disabled")

    def _run_now(self, script_name):
        if self.running:
            return
        self.running = True
        self.run_pipeline_button.config(state="disabled")
        self.run_ojogo_button.config(state="disabled")
        (self.run_pipeline_button if script_name == "main.py" else self.run_ojogo_button).config(
            text="A correr..."
        )
        self.output_box.config(state="normal")
        self.output_box.delete("1.0", "end")
        self.output_box.config(state="disabled")

        thread = threading.Thread(target=self._run_script_thread, args=(script_name,), daemon=True)
        thread.start()

    def _run_script_thread(self, script_name):
        try:
            process = subprocess.Popen(
                [sys.executable, str(BASE_DIR / script_name)],
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
            self.after(0, self._append_output, f"\nErro ao correr {script_name}: {e}\n")
        finally:
            self.after(0, self._on_run_finished)

    def _on_run_finished(self):
        self.running = False
        self.run_pipeline_button.config(state="normal", text="Correr pipeline completo")
        self.run_ojogo_button.config(state="normal", text="Correr só ojogo.pt")

    def _open_logs_folder(self):
        subprocess.run(["explorer", str(LOG_DIR)])


if __name__ == "__main__":
    app = ControlPanel()
    app.mainloop()
