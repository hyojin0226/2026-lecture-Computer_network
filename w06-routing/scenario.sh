#!/usr/bin/env bash
# Week 6 OSPF reconvergence measurements.
# Run from Git Bash (Windows) or another Bash shell with Docker Compose.
set -u
cd "$(dirname "$0")/.." || exit 1
OUT="w06-routing/out"
mkdir -p "$OUT"
DC=(docker compose --profile routing)

capture_routes() {
  for r in r1 r2 r3; do
    echo "===== $r ====="
    "${DC[@]}" exec -T "$r" vtysh -c "show ip route ospf"
  done
}

seconds() { date +%s; }

case "${1:-}" in
  up)
    "${DC[@]}" up -d || exit 1
    echo "라우터 3대를 올렸습니다. OSPF 인접 수립까지 30초 기다립니다."
    sleep 30
    "${DC[@]}" exec -T r1 vtysh -c "show ip ospf neighbor"
    ;;

  routes)
    capture_routes
    ;;

  cut)
    capture_routes | tee "$OUT/route-before.txt"
    echo "r1 eth1 (net_b, r1-r2) 링크를 내립니다."
    START=$(seconds)
    "${DC[@]}" exec -T r1 ip link set eth1 down || exit 1
    converged=0
    for _ in $(seq 1 60); do
      sleep 1
      capture_routes > "$OUT/.routes-current.txt" 2>/dev/null || continue
      if ! cmp -s "$OUT/.routes-current.txt" "$OUT/route-before.txt"; then
        END=$(seconds)
        echo "r1-r2 link down: $((END - START)) seconds (1-second polling resolution)" \
          | tee "$OUT/reconverge.txt"
        cp "$OUT/.routes-current.txt" "$OUT/route-after.txt"
        cat "$OUT/route-after.txt"
        converged=1
        break
      fi
    done
    rm -f "$OUT/.routes-current.txt"
    if [ "$converged" -ne 1 ]; then
      echo "Timeout: no route-table change within 60 seconds after link down." \
        | tee "$OUT/reconverge.txt"
      exit 1
    fi
    ;;

  restore)
    if [ ! -s "$OUT/route-before.txt" ]; then
      echo "Run 'up' and 'cut' first so the pre-cut table is available." >&2
      exit 1
    fi
    capture_routes | tee "$OUT/route-restore-before.txt"
    START=$(seconds)
    "${DC[@]}" exec -T r1 ip link set eth1 up || exit 1
    converged=0
    for _ in $(seq 1 60); do
      sleep 1
      capture_routes > "$OUT/.routes-current.txt" 2>/dev/null || continue
      if cmp -s "$OUT/.routes-current.txt" "$OUT/route-before.txt"; then
        END=$(seconds)
        echo "r1-r2 link restore: $((END - START)) seconds (1-second polling resolution)" \
          | tee "$OUT/restore-reconverge.txt"
        cp "$OUT/.routes-current.txt" "$OUT/route-restored.txt"
        cat "$OUT/route-restored.txt"
        converged=1
        break
      fi
    done
    rm -f "$OUT/.routes-current.txt"
    if [ "$converged" -ne 1 ]; then
      echo "Timeout: route table did not return to its pre-cut state within 60 seconds." \
        | tee "$OUT/restore-reconverge.txt"
      exit 1
    fi
    ;;

  cost)
    capture_routes | tee "$OUT/cost-before.txt"
    echo "r1 eth0 (net_a, r1-r3) OSPF cost를 10에서 100으로 올립니다."
    START=$(seconds)
    "${DC[@]}" exec -T r1 vtysh -c "configure terminal" \
      -c "interface eth0" -c "ip ospf cost 100" || exit 1
    converged=0
    for _ in $(seq 1 60); do
      sleep 1
      capture_routes > "$OUT/.routes-current.txt" 2>/dev/null || continue
      if ! cmp -s "$OUT/.routes-current.txt" "$OUT/cost-before.txt"; then
        END=$(seconds)
        echo "OSPF cost change: $((END - START)) seconds (1-second polling resolution)" \
          | tee "$OUT/cost-reconverge.txt"
        cp "$OUT/.routes-current.txt" "$OUT/cost-after.txt"
        cat "$OUT/cost-after.txt"
        converged=1
        break
      fi
    done
    rm -f "$OUT/.routes-current.txt"
    if [ "$converged" -ne 1 ]; then
      echo "Timeout: no route-table change within 60 seconds after cost change." \
        | tee "$OUT/cost-reconverge.txt"
      exit 1
    fi
    ;;

  down)
    "${DC[@]}" down
    ;;

  *)
    sed -n '2,8p' "$0"
    ;;
esac
