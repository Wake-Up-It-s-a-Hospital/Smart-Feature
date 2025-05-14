// import React, { useEffect, useState } from "react";
// import { db } from "./firebase";
// import { ref, onValue } from "firebase/database";
// import ChartComponent from "./components/ChartComponent";

// function App() {
//   const [weight, setWeight] = useState(0);
//   const [remainingSec, setRemainingSec] = useState(0);

//   const [labels, setLabels] = useState([]);
//   const [graphData, setGraphData] = useState([]);

//   useEffect(() => {
//     const weightRef = ref(db, "infusion/current_weight");
//     const timeRef = ref(db, "infusion/remaining_sec");

//     const interval = setInterval(() => {
//       onValue(weightRef, (snapshot) => {
//         if (snapshot.exists()) {
//           const val = snapshot.val();
//           const now = new Date().toLocaleTimeString();

//           setWeight(val);

//           setLabels((prev) => [...prev.slice(-99), now]); // 최대 100개
//           setGraphData((prev) => [...prev.slice(-99), val]);
//         }
//       }, { onlyOnce: true }); // 실시간 루프 방지
//     }, 1000); // 1초 간격

//     onValue(timeRef, (snapshot) => {
//       if (snapshot.exists()) {
//         setRemainingSec(snapshot.val());
//       }
//     });

//     return () => clearInterval(interval);
//   }, []);

//   return (
//     <div style={{ padding: "2rem", fontFamily: "sans-serif", maxWidth: 800, margin: "auto" }}>
//       <h1>💧 실시간 수액 상태 모니터링</h1>
//       <p>📦 현재 수액 무게: <strong>{weight.toFixed(2)} g</strong></p>
//       <p>⏳ 남은 예상 시간: <strong>{remainingSec.toFixed(1)} 초</strong></p>

//       <div style={{ marginTop: "2rem" }}>
//         <ChartComponent labels={labels} data={graphData} />
//       </div>
//     </div>
//   );
// }

// export default App;


import React from "react";
import { Bell, BatteryCharging, Wifi, UserPlus, User } from "lucide-react";
import './App.css';

export default function Dashboard() {
  return (
    <div className="dashboard">
      {/* Header */}
      <div className="header">
        <input
          type="text"
          placeholder="Search Task"
          className="search-input"
        />
        <div className="header-right">
          <Bell className="icon" />
          <div className="profile">
            <div className="avatar">N</div>
            <span className="username">Nekerworld</span>
          </div>
        </div>
      </div>

      <div className="main-container">
        {/* Sidebar */}
        <div className="sidebar">
          <div className="sidebar-title">Find For You</div>
          <div className="menu">
            <div className="menu-item active">Overview</div>
            <div className="menu-item">Robots</div>
            <div className="menu-item">Camera</div>
            <div className="menu-item">Report</div>
            <div className="menu-item">Projects</div>
          </div>
          <div className="sidebar-footer">
            <div className="section-title">GENERAL</div>
            <div className="menu-item">Settings</div>
            <div className="menu-item">Help</div>
            <div className="menu-item">Logout</div>
          </div>
        </div>

        {/* Main Content */}
        <div className="content">
          {/* Top Cards */}
          <div className="card-grid">
            <div className="card primary">
              <div className="card-content">
                <div className="card-title">My Project 1</div>
                <div className="card-value">24</div>
                <div className="card-unit">m³</div>
              </div>
            </div>
            <div className="card">
              <div className="card-content">
                <div className="card-title">temp proj 4</div>
                <div className="card-value">3</div>
                <div className="card-unit">m³</div>
              </div>
            </div>
            <div className="card">
              <div className="card-content">
                <div className="card-title">temp proj</div>
                <div className="card-value">10</div>
                <div className="card-unit">m³</div>
              </div>
            </div>
            <div className="card">
              <div className="card-content">
                <div className="card-title">wefwd</div>
                <div className="card-value">1</div>
                <div className="card-unit">m³</div>
              </div>
            </div>
            <div className="card">
              <div className="card-content">
                <div className="card-title">yje</div>
                <div className="card-value">43</div>
                <div className="card-unit">m³</div>
              </div>
            </div>
          </div>

          {/* Chart & Robot Info */}
          <div className="info-grid">
            <div className="chart-card">
              <div className="card-content">
                <div className="card-title">탐사 면적</div>
                <div className="chart-placeholder"></div>
              </div>
            </div>

            <div className="info-cards">
              <div className="card">
                <div className="card-content">
                  <div className="card-title">Robots</div>
                  <ul className="robot-list">
                    <li className="robot-item good">Robot 1 <span>65% / 32 Mbps / 17ms</span></li>
                    <li className="robot-item warning">Robot 2 <span>27% / 15 Mbps / 250ms</span></li>
                    <li className="robot-item error">Robot 3 <span>13% / 42 Mbps / 2ms</span></li>
                  </ul>
                </div>
              </div>
              <div className="card">
                <div className="card-content">
                  <div className="card-title">Notifications</div>
                  <div className="notification-list">
                    <div className="notification warning">⚠️ 로봇의 배터리가 낮습니다.</div>
                    <div className="notification error">❗ 로봇의 핑이 매우 높습니다.</div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Bottom Section */}
          <div className="bottom-grid">
            <div className="card">
              <div className="card-content">
                <div className="card-title">Team</div>
                <div className="team-list">
                  <div className="team-member"><User className="icon" /> Nekerworld</div>
                  <div className="team-member"><User className="icon" /> Minecraft</div>
                  <div className="team-member"><User className="icon" /> Da drüben</div>
                  <button className="add-member"><UserPlus className="icon" /> Add Member</button>
                </div>
              </div>
            </div>
            <div className="card">
              <div className="card-content">
                <div className="card-title">Maps</div>
                <div className="map-placeholder"></div>
              </div>
            </div>
            <div className="card">
              <div className="card-content">
                <div className="card-title">Average Battery</div>
                <div className="battery-value">43%</div>
              </div>
            </div>
          </div>

          <div className="stats-grid">
            <div className="card">
              <div className="card-content">
                <div className="card-title">Average Connection</div>
                <div className="connection-value">17 Mbps</div>
              </div>
            </div>
            <div className="card">
              <div className="card-content">
                <div className="card-title">Ping</div>
                <div className="ping-value">153 ms</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}