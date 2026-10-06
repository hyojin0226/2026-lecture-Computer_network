# 4주차 구현과 재현

원본 수업 저장소: https://github.com/codingchild2424/2026-lecture-network-practice
기준 커밋: `0ee3e6622921e1ad049d82bfd7e390bf024ed6aa`

원본 저장소를 복제한 뒤 해당 4주차 파일 안에서 구현하고 학생 제출 저장소에 복사했다. `bench.py`, `test_tasks.py`, `UnreliableChannel`, 제공 `verify()`는 수정하지 않았다.

- Task 1: 순번별 ACK와 타이머를 갖는 Selective Repeat. DATA와 ACK 모두 채널의 공개 send/receive만 사용한다. 8개 창의 맨 앞 번호가 확인된 경우에만 창을 전진시키고, 수신 버퍼는 순서대로만 출력한다.
- Task 2: 기본 대상과 5회 측정 형식을 유지했다. curl 실패/HTTP 오류/바이트 수를 확인하고 시간 제한을 적용했다. 캡처를 좁히기 위한 선택 인수 `--local-port`는 숫자 또는 범위를 받으며, 각 실행에 시작 포트+i를 배정한다. IPv4, HTTP/1.1을 강제했다. 이 포트 옵션은 측정용이며 캡처가 필요 없으면 생략한다.
- Task 3: slow start 임계값 16, ACK마다 가산 증가 0.5/window, 손실 때 0.65배 감소. 지연된 같은 비행 분량의 timeout 때문에 연달아 감소하는 것을 막기 위해 이전 창 크기만큼 ACK를 기다린다. 시뮬레이터 상태를 읽거나 bench 상수를 import하지 않는다. 표준 TCP Reno의 완전한 구현이 아닌 과제 인터페이스용 혼잡 제어다.

## 실행

```powershell
cd w04-tcp
python task1_rdt.py --verify
python task1_rdt.py --verify --seed 999
python task2_measure.py --label "campus wifi"
# 실제 네트워크를 집 Wi-Fi로 전환한 뒤 한 번 실행
python task2_measure.py --label "home wifi"
python bench.py --yours
python extra_checks.py
python test_tasks.py
python ../check.py w04
```

Windows에서는 Python 3.11의 `python`을 사용했다. `tshark`가 PATH에 없으면 현재 셸에서 `$env:PATH = "C:\Program Files\Wireshark;" + $env:PATH`로 추가한다. 파일만 존재하는 검사를 통과해도 관찰 보고서의 해석이 자동 검증되는 것은 아니다.

`extra_checks.py`는 서로 다른 바이트를 가진 140개 입력을 더 높은 손실/중복/재정렬 확률로 검사하고 감속 비율 4개를 비교한다. 원본 verify는 바이트마다 같은 seed로 RNG를 다시 만들어 내용이 반복되므로, 별도의 무작위 내용 검사가 순서 보존 확인에 필요했다. 결과는 out/reliability_checks.json과 out/backoff_comparison.json에 저장한다.
