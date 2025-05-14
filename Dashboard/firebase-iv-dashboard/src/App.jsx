import React, { useEffect, useState } from "react";
import { Bell, BatteryCharging, Wifi, UserPlus, User, Plus, Minus } from "lucide-react";
import { db } from "./firebase";
import { ref, onValue } from "firebase/database";
import ChartComponent from "./components/ChartComponent";
import './App.css';

export default function Dashboard() {
  const [weight, setWeight] = useState(0);
  const [remainingSec, setRemainingSec] = useState(0);
  const [labels, setLabels] = useState([]);
  const [graphData, setGraphData] = useState([]);
  const [cards, setCards] = useState([
    { id: 1, title: "My Project 1", value: 24, unit: "m³" }
  ]);
  const [selectedProjectId, setSelectedProjectId] = useState(1);

  useEffect(() => {
    const weightRef = ref(db, "infusion/current_weight");
    const timeRef = ref(db, "infusion/remaining_sec");

    const interval = setInterval(() => {
      onValue(weightRef, (snapshot) => {
        if (snapshot.exists()) {
          const val = snapshot.val();
          const now = new Date().toLocaleTimeString();

          setWeight(val);
          setLabels((prev) => [...prev.slice(-19), now]); // 최대 20개
          setGraphData((prev) => [...prev.slice(-19), val]); // 최대 20개
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

  const addNewCard = () => {
    const newId = cards.length + 1;
    setCards([...cards, {
      id: newId,
      title: `Project ${newId}`,
      value: Math.floor(Math.random() * 50),
      unit: "m³"
    }]);
    setSelectedProjectId(newId); // 새 프로젝트 추가 시 자동 선택
  };

  const deleteCard = (id) => {
    const newCards = cards.filter(card => card.id !== id);
    setCards(newCards);
    // 삭제된 카드가 선택된 카드였다면, 첫 번째 카드를 선택
    if (id === selectedProjectId && newCards.length > 0) {
      setSelectedProjectId(newCards[0].id);
    }
  };

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
            {cards.map((card) => (
              <div 
                key={card.id} 
                className={`card ${card.id === selectedProjectId ? 'primary' : 'secondary'}`}
                onClick={() => setSelectedProjectId(card.id)}
              >
                {cards.length > 1 && (
                  <button 
                    className="delete-button"
                    onClick={(e) => {
                      e.stopPropagation(); // 카드 클릭 이벤트 전파 방지
                      deleteCard(card.id);
                    }}
                  >
                    <Minus size={16} />
                  </button>
                )}
                <div className="card-content">
                  <div className="card-title">{card.title}</div>
                  <div className="card-value">{card.value}</div>
                  <div className="card-unit">{card.unit}</div>
                </div>
              </div>
            ))}
            <button className="add-card-button" onClick={addNewCard}>
              <Plus size={24} />
            </button>
          </div>

          {/* Chart & Robot Info */}
          <div className="info-grid">
            <div className="chart-card">
              <div className="card-content">
                <div className="card-title">탐사 면적</div>
                <div className="chart-container">
                  <ChartComponent labels={labels} data={graphData} />
                </div>
                <div className="weight-info">
                  <p>📦 현재 수액 무게: <strong>{weight.toFixed(2)} g</strong></p>
                  <p>⏳ 남은 예상 시간: <strong>{remainingSec.toFixed(1)} 초</strong></p>
                </div>
              </div>
            </div>

            <div className="robots-card card">
              <div className="card-content">
                <div className="card-title">Robots</div>
                <ul className="robot-list">
                  <li className="robot-item good">Robot 1 <span>65% / 32 Mbps / 17ms</span></li>
                  <li className="robot-item warning">Robot 2 <span>27% / 15 Mbps / 250ms</span></li>
                  <li className="robot-item error">Robot 3 <span>13% / 42 Mbps / 2ms</span></li>
                </ul>
              </div>
            </div>

            <div className="notifications-card card">
              <div className="card-content">
                <div className="card-title">Notifications</div>
                <div className="notification-list">
                  <div className="notification warning">⚠️ 로봇의 배터리가 낮습니다.</div>
                  <div className="notification error">❗ 로봇의 핑이 매우 높습니다.</div>
                </div>
              </div>
            </div>

            <div className="team-card card">
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

            <div className="status-card card">
              <div className="card-content status-content">
                <div className="card-title">Status</div>
                <div className="status-list">
                  <div className="status-item">
                    <span className="status-label">Battery</span>
                    <span className="status-value">43%</span>
                  </div>
                  <div className="status-item">
                    <span className="status-label">Connection</span>
                    <span className="status-value">17 Mbps</span>
                  </div>
                  <div className="status-item">
                    <span className="status-label">Ping</span>
                    <span className="status-value">153 ms</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}