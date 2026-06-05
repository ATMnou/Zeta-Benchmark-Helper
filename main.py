from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText

import pyarrow.parquet as pq


APP_DIR = Path(__file__).resolve().parent
PROGRESS_FILE = APP_DIR / "grading_progress.json"
OPTION_LABELS = "ABCDEFGHIJ"


@dataclass
class QuestionRecord:
	global_index: int
	split: str
	source_file: str
	file_index: int
	question_id: int | str | None
	category: str
	src: str
	question: str
	options: list[str]
	answer_index: int
	answer_label: str
	answer_text: str

	def build_prompt_text(self) -> str:
		lines = [self.question.strip(), "", "선택지:"]
		for index, option in enumerate(self.options):
			lines.append(f"{index + 1}. {option}")
		return "\n".join(lines)


class BenchmarkApp:
	def __init__(self, root: tk.Tk) -> None:
		self.root = root
		self.root.title("MMLU-ProX-Lite Benchmark Helper")
		self.root.geometry("1320x860")

		self.records = self._load_records()
		if not self.records:
			raise RuntimeError("표시할 문제가 없습니다.")

		self.progress = self._load_progress()
		self.current_index = self._resolve_initial_index()
		self.status_var = tk.StringVar(value="")
		self.answer_number_var = tk.StringVar(value="")
		self.answer_text_var = tk.StringVar(value="")
		self.meta_var = tk.StringVar(value="")
		self.correct_var = tk.BooleanVar(value=False)
		self.incorrect_var = tk.BooleanVar(value=False)

		self._build_ui()
		self._render_question()
		self._refresh_scoreboard()

	def _load_records(self) -> list[QuestionRecord]:
		records: list[QuestionRecord] = []
		parquet_files = sorted(APP_DIR.glob("*.parquet"))
		if not parquet_files:
			raise FileNotFoundError("현재 폴더에 parquet 파일이 없습니다.")

		global_index = 0
		for parquet_path in parquet_files:
			split = parquet_path.stem.split("-")[0]
			rows = pq.read_table(parquet_path).to_pylist()
			for file_index, row in enumerate(rows):
				options = self._extract_options(row)
				answer_index = int(row.get("answer_index", -1))
				answer_text = options[answer_index] if 0 <= answer_index < len(options) else ""
				answer_label = OPTION_LABELS[answer_index] if 0 <= answer_index < len(OPTION_LABELS) else "?"
				records.append(
					QuestionRecord(
						global_index=global_index,
						split=split,
						source_file=parquet_path.name,
						file_index=file_index,
						question_id=row.get("question_id"),
						category=str(row.get("category") or "uncategorized"),
						src=str(row.get("src") or ""),
						question=str(row.get("question") or ""),
						options=options,
						answer_index=answer_index,
						answer_label=str(row.get("answer") or answer_label),
						answer_text=answer_text,
					)
				)
				global_index += 1
		return records

	def _extract_options(self, row: dict) -> list[str]:
		options: list[str] = []
		for index in range(10):
			value = row.get(f"option_{index}")
			if value is None:
				continue
			text = str(value).strip()
			if text:
				options.append(text)
		return options

	def _load_progress(self) -> dict:
		default_progress = {
			"version": 1,
			"current_index": 0,
			"answers": {},
		}
		if not PROGRESS_FILE.exists():
			return default_progress

		try:
			loaded = json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
		except (json.JSONDecodeError, OSError):
			messagebox.showwarning("채점 파일 오류", "grading_progress.json을 읽지 못해 새로 시작합니다.")
			return default_progress

		answers = loaded.get("answers")
		if not isinstance(answers, dict):
			answers = {}
		return {
			"version": 1,
			"current_index": int(loaded.get("current_index", 0) or 0),
			"answers": answers,
		}

	def _resolve_initial_index(self) -> int:
		if not self.records:
			return 0
		saved_index = int(self.progress.get("current_index", 0) or 0)
		return max(0, min(saved_index, len(self.records) - 1))

	def _build_ui(self) -> None:
		self.root.columnconfigure(0, weight=3)
		self.root.columnconfigure(1, weight=2)
		self.root.rowconfigure(0, weight=1)

		left_frame = ttk.Frame(self.root, padding=12)
		left_frame.grid(row=0, column=0, sticky="nsew")
		left_frame.columnconfigure(0, weight=1)
		left_frame.rowconfigure(1, weight=1)

		header_frame = ttk.Frame(left_frame)
		header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
		header_frame.columnconfigure(0, weight=1)

		ttk.Label(header_frame, textvariable=self.meta_var, font=("Malgun Gothic", 11, "bold")).grid(
			row=0, column=0, sticky="w"
		)
		ttk.Label(header_frame, textvariable=self.status_var, foreground="#1f5f8b").grid(
			row=1, column=0, sticky="w", pady=(4, 0)
		)

		self.prompt_text = ScrolledText(left_frame, wrap="word", font=("Malgun Gothic", 11))
		self.prompt_text.grid(row=1, column=0, sticky="nsew")

		prompt_button_frame = ttk.Frame(left_frame)
		prompt_button_frame.grid(row=2, column=0, sticky="ew", pady=(8, 0))
		prompt_button_frame.columnconfigure(4, weight=1)

		ttk.Button(prompt_button_frame, text="복사", command=self._copy_prompt).grid(row=0, column=0, padx=(0, 6))
		ttk.Button(prompt_button_frame, text="이전 문제", command=self._go_previous).grid(row=0, column=1, padx=6)
		ttk.Button(prompt_button_frame, text="다음 문제", command=self._go_next).grid(row=0, column=2, padx=6)
		ttk.Button(prompt_button_frame, text="저장", command=self._save_progress).grid(row=0, column=3, padx=6)

		right_frame = ttk.Frame(self.root, padding=(0, 12, 12, 12))
		right_frame.grid(row=0, column=1, sticky="nsew")
		right_frame.columnconfigure(0, weight=1)
		right_frame.rowconfigure(3, weight=1)

		answer_frame = ttk.LabelFrame(right_frame, text="정답 정보", padding=12)
		answer_frame.grid(row=0, column=0, sticky="ew")
		answer_frame.columnconfigure(1, weight=1)

		ttk.Label(answer_frame, text="정답 번호").grid(row=0, column=0, sticky="w", pady=2)
		ttk.Entry(answer_frame, textvariable=self.answer_number_var, state="readonly").grid(
			row=0, column=1, sticky="ew", pady=2
		)
		ttk.Label(answer_frame, text="정답").grid(row=1, column=0, sticky="nw", pady=2)
		ttk.Entry(answer_frame, textvariable=self.answer_text_var, state="readonly").grid(
			row=1, column=1, sticky="ew", pady=2
		)

		grading_frame = ttk.LabelFrame(right_frame, text="채점", padding=12)
		grading_frame.grid(row=1, column=0, sticky="ew", pady=(12, 0))
		grading_frame.columnconfigure(0, weight=1)
		grading_frame.columnconfigure(1, weight=1)

		ttk.Checkbutton(
			grading_frame,
			text="정답",
			variable=self.correct_var,
			command=lambda: self._set_judgement("correct"),
		).grid(row=0, column=0, sticky="w")
		ttk.Checkbutton(
			grading_frame,
			text="오답",
			variable=self.incorrect_var,
			command=lambda: self._set_judgement("incorrect"),
		).grid(row=0, column=1, sticky="w")

		help_text = (
			"정답 또는 오답을 체크하면 즉시 grading_progress.json에 저장됩니다.\n"
			"체크를 다시 누르면 해당 문제의 채점이 해제됩니다."
		)
		ttk.Label(grading_frame, text=help_text, foreground="#555555", justify="left").grid(
			row=1, column=0, columnspan=2, sticky="w", pady=(8, 0)
		)

		summary_frame = ttk.LabelFrame(right_frame, text="카테고리 점수", padding=12)
		summary_frame.grid(row=2, column=0, sticky="nsew", pady=(12, 0))
		summary_frame.columnconfigure(0, weight=1)
		summary_frame.rowconfigure(0, weight=1)

		columns = ("category", "score", "graded", "total")
		self.score_tree = ttk.Treeview(summary_frame, columns=columns, show="headings", height=18)
		self.score_tree.grid(row=0, column=0, sticky="nsew")
		headings = {
			"category": ("카테고리", 180),
			"score": ("현재 점수", 90),
			"graded": ("채점 수", 90),
			"total": ("총 문제 수", 90),
		}
		for column, (title, width) in headings.items():
			self.score_tree.heading(column, text=title)
			self.score_tree.column(column, width=width, anchor="center")

		scrollbar = ttk.Scrollbar(summary_frame, orient="vertical", command=self.score_tree.yview)
		scrollbar.grid(row=0, column=1, sticky="ns")
		self.score_tree.configure(yscrollcommand=scrollbar.set)

	def _render_question(self) -> None:
		record = self.records[self.current_index]
		self.meta_var.set(
			f"문제 {self.current_index + 1}/{len(self.records)} | split: {record.split} | "
			f"category: {record.category} | source: {record.source_file} | qid: {record.question_id}"
		)
		self.status_var.set(self._build_status_text(record))
		self.answer_number_var.set(f"{record.answer_index + 1} ({record.answer_label})")
		self.answer_text_var.set(record.answer_text)

		self.prompt_text.configure(state="normal")
		self.prompt_text.delete("1.0", tk.END)
		self.prompt_text.insert("1.0", record.build_prompt_text())
		self.prompt_text.configure(state="normal")

		judgement = self.progress.get("answers", {}).get(str(record.global_index), {}).get("judgement")
		self.correct_var.set(judgement == "correct")
		self.incorrect_var.set(judgement == "incorrect")

		current_category = record.category
		for item_id in self.score_tree.get_children():
			values = self.score_tree.item(item_id, "values")
			if values and values[0] == current_category:
				self.score_tree.selection_set(item_id)
				self.score_tree.see(item_id)
				break

	def _build_status_text(self, record: QuestionRecord) -> str:
		answers = self.progress.get("answers", {})
		judged_count = len(answers)
		judgement = answers.get(str(record.global_index), {}).get("judgement")
		label_map = {
			None: "미채점",
			"correct": "정답 처리됨",
			"incorrect": "오답 처리됨",
		}
		return f"현재 상태: {label_map.get(judgement, '미채점')} | 전체 채점: {judged_count}/{len(self.records)}"

	def _copy_prompt(self) -> None:
		text = self.prompt_text.get("1.0", tk.END).strip()
		self.root.clipboard_clear()
		self.root.clipboard_append(text)
		self.status_var.set(f"클립보드에 복사됨 | 전체 채점: {len(self.progress.get('answers', {}))}/{len(self.records)}")

	def _go_previous(self) -> None:
		if self.current_index > 0:
			self.current_index -= 1
			self.progress["current_index"] = self.current_index
			self._save_progress(show_message=False)
			self._render_question()

	def _go_next(self) -> None:
		if self.current_index < len(self.records) - 1:
			self.current_index += 1
			self.progress["current_index"] = self.current_index
			self._save_progress(show_message=False)
			self._render_question()

	def _set_judgement(self, judgement: str) -> None:
		record = self.records[self.current_index]
		key = str(record.global_index)
		answers = self.progress.setdefault("answers", {})
		existing = answers.get(key, {}).get("judgement")

		if judgement == "correct":
			is_checked = self.correct_var.get()
			self.incorrect_var.set(False)
		else:
			is_checked = self.incorrect_var.get()
			self.correct_var.set(False)

		if is_checked and existing != judgement:
			answers[key] = self._build_answer_payload(record, judgement)
		elif is_checked and existing == judgement:
			answers.pop(key, None)
			self.correct_var.set(False)
			self.incorrect_var.set(False)
		elif not is_checked and existing == judgement:
			answers.pop(key, None)

		self.progress["current_index"] = self.current_index
		self._save_progress(show_message=False)
		self._refresh_scoreboard()
		self._render_question()

	def _build_answer_payload(self, record: QuestionRecord, judgement: str) -> dict:
		return {
			"judgement": judgement,
			"split": record.split,
			"source_file": record.source_file,
			"file_index": record.file_index,
			"question_id": record.question_id,
			"category": record.category,
			"src": record.src,
			"answer_index": record.answer_index,
			"answer_label": record.answer_label,
			"answer_text": record.answer_text,
		}

	def _refresh_scoreboard(self) -> None:
		category_totals: dict[str, int] = defaultdict(int)
		category_graded: dict[str, int] = defaultdict(int)
		category_correct: dict[str, int] = defaultdict(int)

		for record in self.records:
			category_totals[record.category] += 1

		for answer in self.progress.get("answers", {}).values():
			category = str(answer.get("category") or "uncategorized")
			category_graded[category] += 1
			if answer.get("judgement") == "correct":
				category_correct[category] += 1

		self.score_tree.delete(*self.score_tree.get_children())

		total_correct = 0
		total_graded = 0
		total_questions = len(self.records)
		for category in sorted(category_totals):
			score = category_correct[category]
			graded = category_graded[category]
			total = category_totals[category]
			total_correct += score
			total_graded += graded
			self.score_tree.insert("", tk.END, values=(category, score, graded, total))

		self.score_tree.insert("", 0, values=("전체", total_correct, total_graded, total_questions))

	def _save_progress(self, show_message: bool = True) -> None:
		self.progress["current_index"] = self.current_index
		PROGRESS_FILE.write_text(
			json.dumps(self.progress, ensure_ascii=False, indent=2),
			encoding="utf-8",
		)
		if show_message:
			messagebox.showinfo("저장 완료", f"채점 현황을 저장했습니다.\n{PROGRESS_FILE.name}")


def main() -> None:
	root = tk.Tk()
	try:
		app = BenchmarkApp(root)
	except Exception as exc:
		root.withdraw()
		messagebox.showerror("실행 오류", str(exc))
		root.destroy()
		return

	root.bind("<Left>", lambda _event: app._go_previous())
	root.bind("<Right>", lambda _event: app._go_next())
	root.mainloop()


if __name__ == "__main__":
	main()
