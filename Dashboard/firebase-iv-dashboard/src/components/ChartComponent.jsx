import React from "react";
import { Line } from "react-chartjs-2";
import { Chart, CategoryScale, LinearScale, LineElement, PointElement, Tooltip } from "chart.js";

// Chart.js 모듈 등록 (필수)
Chart.register(CategoryScale, LinearScale, LineElement, PointElement, Tooltip);

function ChartComponent({ labels, data }) {
  const chartData = {
    labels,
    datasets: [
      {
        label: "수액 무게 (g)",
        data,
        borderColor: "rgb(75, 192, 192)",
        backgroundColor: "rgb(75, 192, 192)",
        tension: 0.3,
        pointRadius: 6, // 점 크기
        pointHoverRadius: 9, // 호버 시 점 크기
        pointBackgroundColor: "#047857",
        pointBorderColor: "#fff",
        pointBorderWidth: 2,
        fill: false,
      },
    ],
  };

  const options = {
    responsive: true,
    animation: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        enabled: true,
        callbacks: {
          label: function(context) {
            return `무게: ${context.parsed.y} g`;
          },
        },
        backgroundColor: '#047857',
        titleColor: '#fff',
        bodyColor: '#fff',
        displayColors: false,
        caretSize: 6,
        padding: 10,
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        title: {
          display: false, // y축 라벨 제거
        },
        grid: {
          display: false, // y축 grid 제거
        },
        border: {
          display: false, // y축 축선 제거
        },
        ticks: {
          display: false, // y축 눈금 제거
        },
      },
      x: {
        ticks: {
          display: false, // x축 눈금 제거
        },
        grid: {
          display: false, // x축 grid 제거
        },
        border: {
          display: false, // x축 축선 제거
        },
      },
    },
    elements: {
      line: {
        borderWidth: 3,
      },
    },
  };

  return <Line data={chartData} options={options} />;
}

export default ChartComponent;
