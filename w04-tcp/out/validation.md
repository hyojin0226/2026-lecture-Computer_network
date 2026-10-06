# 최종 검증

2026-10-06, 제출 저장소의 w04-tcp에서 실행했다.

- `python test_tasks.py`: **8 passed, 0 failed, 1 skipped**. 건너뛴 항목은 사람이 채점하는 R5 관찰 설명뿐이다. tshark가 캡처의 SYN 2개를 실제로 읽었고 두 네트워크와 각 5회 측정도 통과했다.
- `python ../check.py w04`: **Format check passed**.
- `python bench.py --yours`: **strong**. Goodput 972.75/1000 slots(기준의 98.58%), 손실 0.153%, 평균 큐 4.641.
- 앞서 시행한 추가 신뢰성 검사 140개 전부 통과. 재현: `python extra_checks.py`.
- `bench.py`, `test_tasks.py`는 원본과 동일하고 `UnreliableChannel` 및 `verify()`의 AST도 원본과 동일함을 확인했다.
- 제출 캡처는 직접 실행한 학교 Wi-Fi 측정의 첫 TCP 연결만 포함한다. 패킷 번호 1~4209이며 본문은 최대 128바이트 캡처로 제한했다.

Windows 사용자 환경에서 `C:\Program Files\Wireshark`를 해당 프로세스 PATH에 추가하여 최종 테스트를 수행했다. 샌드박스의 tshark 검색 제한으로 발생한 이전 skip은 최종 결과에 해당하지 않는다.
