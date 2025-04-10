import React, { useEffect, useState } from "react";
import { db } from "./firebase";
import { ref, onValue } from "firebase/database";
import ChartComponent from "./components/ChartComponent";

function App() {
  const [weight, setWeight] = useState(0);
  const [remainingSec, setRemainingSec] = useState(0);

  const [labels, setLabels] = useState([]);
  const [graphData, setGraphData] = useState([]);

  useEffect(() => {
    const weightRef = ref(db, "infusion/current_weight");
    const timeRef = ref(db, "infusion/remaining_sec");

    const interval = setInterval(() => {
      onValue(weightRef, (snapshot) => {
        if (snapshot.exists()) {
          const val = snapshot.val();
          const now = new Date().toLocaleTimeString();

          setWeight(val);

          setLabels((prev) => [...prev.slice(-99), now]); // 최대 100개
          setGraphData((prev) => [...prev.slice(-99), val]);
        }
      }, { onlyOnce: true }); // 실시간 루프 방지
    }, 1000); // 1초 간격

    onValue(timeRef, (snapshot) => {
      if (snapshot.exists()) {
        setRemainingSec(snapshot.val());
      }
    });

    return () => clearInterval(interval);
  }, []);

  return (
    <div style={{ padding: "2rem", fontFamily: "sans-serif", maxWidth: 800, margin: "auto" }}>
      <h1>💧 실시간 수액 상태 모니터링</h1>
      <p>📦 현재 수액 무게: <strong>{weight.toFixed(2)} g</strong></p>
      <p>⏳ 남은 예상 시간: <strong>{remainingSec.toFixed(1)} 초</strong></p>

      <div style={{ marginTop: "2rem" }}>
        <ChartComponent labels={labels} data={graphData} />
      </div>
    </div>
  );
}

export default App;
