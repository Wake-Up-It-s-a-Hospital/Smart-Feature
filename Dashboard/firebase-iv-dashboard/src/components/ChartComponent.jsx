import React from "react";
import { Line } from "react-chartjs-2";
import { Chart, CategoryScale, LinearScale, LineElement, PointElement } from "chart.js";

// Chart.js 모듈 등록 (필수)
Chart.register(CategoryScale, LinearScale, LineElement, PointElement);

function ChartComponent({ labels, data }) {
  const chartData = {
    labels,
    datasets: [
      {
        label: "수액 무게 (g)",
        data,
        borderColor: "rgb(75, 192, 192)",
        tension: 0.3,
        pointRadius: 0,
      },
    ],
  };

  const options = {
    responsive: true,
    animation: false,
    scales: {
      y: {
        beginAtZero: true,
        title: {
          display: true,
          text: "무게 (g)",
        },
      },
      x: {
        ticks: {
          display: false, // x축 시간 안 보이게 처리
        },
      },
    },
  };

  return <Line data={chartData} options={options} />;
}

export default ChartComponent;
