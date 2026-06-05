# Zeta 모델의 MMLU-ProX-Lite 벤치마크 결과

## 벤치마크 방법:

1. 벤치마크 전용 비공개 플룻 작성.
2. CoT 적용 / 할루시네이션 및 RP 금지 프롬프트 사용.
3. Tkinter로 전용 헬퍼를 작성해 체점 시스템 및 복사 붙여넣기 사용, 봇이나 매크로 일절 사용하지 않았음.

## 채점 관련:

1. 할루시네이션이 극심한 Zeta 모델 특성상, 할루시네이션(문제를 풀지 않았거나, RP 진행 등) 발생 시 2회까지 재시도 후 3회째 할루시네이션 발생 시 오답 처리.
2. 복수 정답이나 정답 없음, 또는 정답 번호와 정답 내용이 틀렸을 시 오답 처리.

## 벤치마크로 사용된 데이터셋:

ko 언어 사용
https://huggingface.co/datasets/li-lab/MMLU-ProX-Lite/tree/main

## 총 점수:

85/658 (12.9%)

## 카테고리별 점수

Biolog : 5/41 (12%)
Business: 8/45 (17%)
Chemistry: 5/61 (8%)
Computer Science: 4/25 (16%)
Economics: 9/47 (19%)
Engineering: 5/53 (9%)
Health: 2/40 (5%)
History: 2/24 (8%)
Law: 6/53 (11%)
Math: 9/73 (12%)
Other: 8/51 (15%)
Philosophy: 5/30 (16%)
Physics: 7/70 (10%)
Psychology: 10/45 (22%)
