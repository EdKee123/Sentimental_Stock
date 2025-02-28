// Global chart variable
let chart = null;
// Flag to prevent multiple simultaneous sentiment fetches
//let isFetchingSentiment = false;

// Populate companies dropdown from API
async function populateCompanies() {
  try {
    const response = await fetch('http://127.0.0.1:8000/companies');
    const data = await response.json();
    const dropdown = document.getElementById("companiesDropdown");
    dropdown.innerHTML = ""; // Clear existing items

    data.companies.forEach(company => {
      const link = document.createElement("a");
      link.href = "#";
      link.textContent = company;
      link.addEventListener("click", (e) => {
        e.preventDefault();
        const selectedElem = document.getElementById("selectedCompany");
        selectedElem.textContent = company;
        selectedElem.dataset.value = company;
        // Hide the dropdown after selection
        dropdown.style.display = "none";
      });
      dropdown.appendChild(link);
    });
  } catch (error) {
    console.error("Error fetching companies:", error);
  }
}

// Toggle companies dropdown using computed style
function toggleCompaniesDropdown() {
  const dropdown = document.getElementById("companiesDropdown");
  const currentDisplay = window.getComputedStyle(dropdown).display;
  dropdown.style.display = currentDisplay === "none" ? "block" : "none";
}

/*========================
  Stock Data Functions
========================*/
async function fetchStockData(company) {
  try {
    const url = `http://127.0.0.1:8000/stockdata?company=${encodeURIComponent(company)}`;
    const response = await fetch(url);
    if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
    const result = await response.json();
    console.log("Stock data received:", result);
    updateChartWithStockData(result.data, result.range, result.x_max);
  } catch (error) {
    console.error("Error fetching stock data:", error);
  }
}

function updateChartWithStockData(data, range, xMax) {
  // Convert epoch timestamps (seconds) to Date objects
  const xLabels = data.map(item => new Date(item.timestamp * 1000));
  const yValues = data.map(item => item.adj_close);

  if (chart) {
    chart.destroy();
    chart = null;
  }
  
  const ctx = document.getElementById("chartCanvas").getContext("2d");
  chart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: xLabels,
      datasets: [{
        label: 'Adjusted Close ($)',
        data: yValues,
        borderColor: 'blue',
        backgroundColor: 'transparent',
        fill: false,
        pointRadius: 3,    // Smaller points
        tension: 0.4       // Smoother curve
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          type: 'time',  // Time scale for human-readable dates
          time: {
            unit: 'day',
            tooltipFormat: 'MMM d, yyyy HH:mm'
          },
          // Force the stock chart from Dec 3, 2024 to now
          min: new Date("2024-12-03T00:00:00"),
          max: new Date(),
          title: { display: true, text: 'Date' }
        },
        y: {
          min: range.min,
          max: range.max,
          title: { display: true, text: 'Price ($)' }
        }
      },
      plugins: {
        zoom: {
          pan: { enabled: true, mode: 'x', modifierKey: 'shift' },
          zoom: { wheel: { enabled: true }, pinch: { enabled: true }, mode: 'x' }
        }
      }
    }
  });
}

/*=============================
  Sentiment Data Functions
=============================*/
async function fetchSentimentData(company) {
  // Prevent multiple calls
  // if (isFetchingSentiment) return;
  // isFetchingSentiment = true;
  try {
    const url = `http://127.0.0.1:8000/sentimentdata?company=${encodeURIComponent(company)}`;
    console.log("Fetching Sentiment Data from:", url);
    const response = await fetch(url);
    if (!response.ok){
      throw new Error(`HTTP error! Status: ${response.status}`);
    }
    const result = await response.json();
    console.log("Sentiment data received:", result);
    updateChartWithSentimentData(result.data);
  } catch (error) {
    console.error("Error fetching sentiment data:", error);
  } //finally {
    //isFetchingSentiment = false;
  //}
}

function updateChartWithSentimentData(data) {
  // Convert epoch timestamps (seconds) to Date objects
  const xLabels = data.map(item => item.timestamp);
  //const xLabels = data.map(item => new Date(item.timestamp * 1000));
  const scores = data.map(item => item.score);

  // Prepare tooltips for each bar
  const tooltipTexts = data.map(item =>
    `${item.newssite}\nPositive: ${item.breakdown.positive}\nNeutral: ${item.breakdown.neutral}\nNegative: ${item.breakdown.negative}`
  );

  if (chart) {
    chart.destroy();
    chart = null;
  }
  
  const ctx = document.getElementById("chartCanvas").getContext("2d");
  chart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: xLabels,
      datasets: [{
        label: 'Sentiment Score',
        data: scores,
        backgroundColor: scores.map(val => val >= 0 ? 'green' : 'red')
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          title: { display: true, text: 'Timestamp' }
        },
        y: {
          min: -1,
          max: 1,
          title: { display: true, text: 'Sentiment Score' }
        }
      },
      plugins: {
        tooltip: {
          callbacks: {
            label: function(context) {
              return tooltipTexts[context.dataIndex];
            }
          }
        },
        zoom: {
          pan: { enabled: true, mode: 'x', modifierKey: 'shift' },
          zoom: { wheel: { enabled: true }, pinch: { enabled: true }, mode: 'x' }
        }
      }
    }
  });
}

/*==================================
  Show predictions as popups
==================================*/
function showPopupsSequentially(predictions) {
  let index = 0;
  function showNext() {
    if (index >= predictions.length) return;
    const p = predictions[index];
    const popup = document.createElement("div");
    popup.classList.add("prediction-popup");
    
    // Color code by prediction
    let bgColor = "yellow"; // default (Same)
    if (p.prediction === "Up") bgColor = "green";
    else if (p.prediction === "Down") bgColor = "red";
    popup.style.backgroundColor = bgColor;
    
    const upPercent = (p.prob_up * 100).toFixed(1);
    const downPercent = (p.prob_down * 100).toFixed(1);
    const samePercent = (p.prob_same * 100).toFixed(1);
    
    popup.innerHTML = `
      <strong>Company:</strong> ${p.company} <br/>
      <strong>Newssite:</strong> ${p.newssite} <br/>
      <strong>Prediction:</strong> ${p.prediction} <br/>
      (Up=${upPercent}%, Down=${downPercent}%, Same=${samePercent}%)
    `;
    popup.style.position = "fixed";
    popup.style.top = "20px";
    popup.style.right = "20px";
    popup.style.padding = "10px 15px";
    popup.style.color = "#000";
    popup.style.borderRadius = "5px";
    popup.style.zIndex = 9999;
    popup.style.boxShadow = "0 0 8px rgba(0,0,0,0.3)";
    document.body.appendChild(popup);
    setTimeout(() => {
      document.body.removeChild(popup);
      index++;
      showNext();
    }, 3000);
  }
  showNext();
}

/*===============================================
  DOMContentLoaded: Attach event listeners
===============================================*/
document.addEventListener("DOMContentLoaded", () => {
  // Initialize a placeholder chart
  const ctx = document.getElementById("chartCanvas").getContext("2d");
  chart = new Chart(ctx, {
    type: "line",
    data: {
      labels: ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
      datasets: [{
        label: "Sample Data",
        data: [12, 19, 3, 5, 2, 3],
        borderColor: "blue",
        fill: false
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false
    }
  });

  // Toggle companies dropdown
  document.getElementById("companiesBtn").addEventListener("click", (e) => {
    e.preventDefault();
    toggleCompaniesDropdown();
  });

  // Live button to run pipeline
  document.getElementById("liveBtn").addEventListener("click", async (e) => {
    e.preventDefault();
    const loader = document.getElementById("loader");
    loader.style.display = "block";
    try {
      const response = await fetch("http://127.0.0.1:8000/runAll", { method: "POST" });
      if (!response.ok) throw new Error(`runAll error: ${response.status}`);
      const data = await response.json();
      console.log("runAll response:", data);
      if (data.status !== "ok") {
        alert("Pipeline error: " + data.message);
        return;
      }
      const predictions = data.predictions || [];
      if (predictions.length === 0) {
        alert("No final predictions found.");
        return;
      }
      showPopupsSequentially(predictions);
    } catch (err) {
      console.error("Error in liveBtn handler:", err);
      alert("Error running pipeline: " + err.message);
    } finally {
      loader.style.display = "none";
    }
  });

  // Check button
  document.getElementById("checkBtn").addEventListener("click", (e) => {
    e.preventDefault();
    const userText = document.getElementById("checkArea").value;
    alert("Check button clicked with input: " + userText);
  });

  // Populate companies
  populateCompanies();

  // Stock Data button
  document.getElementById("stockDataButton").addEventListener("click", (e) => {
    e.preventDefault();
    const selectedCompany = document.getElementById("selectedCompany").dataset.value;
    if (!selectedCompany) {
      alert("Please select a company first!");
      return;
    }
    fetchStockData(selectedCompany);
  });

  // Sentiment Articles button
  document.getElementById("sentimentDataButton").addEventListener("click", (e) => {
    e.preventDefault();
    const selectedCompany = document.getElementById("selectedCompany").dataset.value;
    if (!selectedCompany) {
      alert("Please select a company first!");
      return;
    }
    fetchSentimentData(selectedCompany);
  });

  // Reset Zoom button
  document.getElementById("resetZoomBtn").addEventListener("click", () => {
    if (chart) chart.resetZoom();
  });
});
