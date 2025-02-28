// Global chart variable
let chart = null;

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
      link.addEventListener("click", () => {
        // Set the selected company display and data attribute
        const selectedElem = document.getElementById("selectedCompany");
        selectedElem.textContent = company;
        selectedElem.dataset.value = company;
        // Hide the companies dropdown after selection
        dropdown.style.display = "none";
      });
      dropdown.appendChild(link);
    });
  } catch (error) {
    console.error("Error fetching companies:", error);
  }
}

// Toggle companies dropdown visibility
function toggleCompaniesDropdown() {
  const dropdown = document.getElementById("companiesDropdown");
  if (dropdown.style.display === "block") {
    dropdown.style.display = "none";
  } else {
    dropdown.style.display = "block";
  }
}

// Fetch stock data and update chart as a line chart
async function fetchStockData(company) {
  try {
    const response = await fetch(`http://127.0.0.1:8000/stockdata?company=${encodeURIComponent(company)}`);
    if (!response.ok) {
      throw new Error(`HTTP error! Status: ${response.status}`);
    }
    const result = await response.json();
    console.log("Stock data received:", result);
    updateChartWithStockData(result.data, result.range, result.x_max);
  } catch (error) {
    console.error("Error fetching stock data:", error);
  }
}

function updateChartWithStockData(data, range, xMax) {
  const xLabels = data.map(item => item.timestamp);
  const yValues = data.map(item => item.adj_close);

  // Destroy previous chart if exists
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
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          type: 'linear',
          min:  1733184001,  // Fixed starting point
          max: xMax,      // Maximum timestamp from API
          title: { display: true, text: 'Timestamp' }
        },
        y: {
          min: range.min,
          max: range.max,
          title: { display: true, text: 'Price ($)' }
        }
      },
      plugins: {
        zoom: {
          pan: {
            enabled: true,
            mode: 'x',
            modifierKey: 'shift'
          },
          zoom: {
            wheel: { enabled: true },
            pinch: { enabled: true },
            mode: 'x'
          }
        }
      }
    }
  });
}

// Fetch sentiment data and update chart as a bar chart
async function fetchSentimentData(company) {
  try {
    const url = `http://127.0.0.1:8000/sentimentdata?company=${encodeURIComponent(company)}`;
    console.log("Fetching Sentiment Data from:", url);
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`HTTP error! Status: ${response.status}`);
    }
    const result = await response.json();
    console.log("Sentiment data received:", result);
    updateChartWithSentimentData(result.data);
  } catch (error) {
    console.error("Error fetching sentiment data:", error);
  }
}

function updateChartWithSentimentData(data) {
  const xLabels = data.map(item => item.timestamp);
  const scores = data.map(item => item.score);
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
        backgroundColor: scores.map(val => val >= 0 ? 'green' : 'red'),
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
            label: function (context) {
              return tooltipTexts[context.dataIndex];
            }
          }
        },
        zoom: {
          pan: {
            enabled: true,
            mode: 'x',
            modifierKey: 'shift'
          },
          zoom: {
            wheel: { enabled: true },
            pinch: { enabled: true },
            mode: 'x'
          }
        }
      }
    }
  });
}

// Set up event listeners once the DOM is loaded
document.addEventListener("DOMContentLoaded", () => {
  // Initialize a placeholder chart (optional)
  const ctx = document.getElementById("chartCanvas").getContext("2d");
  chart = new Chart(ctx, {
    type: "line",
    data: {
      labels: ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
      datasets: [{
        label: "Sample Data",
        data: [12, 19, 3, 5, 2, 3],
        borderColor: "blue",
        fill: false,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
    },
  });

  // Toggle companies dropdown when clicking the button
  document.getElementById("companiesBtn").addEventListener("click", toggleCompaniesDropdown);

  // Live and Check button event listeners
  document.getElementById("liveBtn").addEventListener("click", () => {
    alert("Live button clicked!");
  });
  document.getElementById("checkBtn").addEventListener("click", () => {
    const userText = document.getElementById("checkArea").value;
    alert("Check button clicked with input: " + userText);
  });

  // Reset Zoom button event listener
  document.getElementById("resetZoomBtn").addEventListener("click", () => {
    if (chart) {
      chart.resetZoom();
    }
  });

  // Populate companies dropdown
  populateCompanies();

  // Stock Data button event listener
  document.getElementById("stockDataButton").addEventListener("click", () => {
    const selectedCompany = document.getElementById("selectedCompany").dataset.value;
    if (!selectedCompany) {
      alert("Please select a company first!");
      return;
    }
    fetchStockData(selectedCompany);
  });

  // Sentiment Articles button event listener
  document.getElementById("sentimentDataButton").addEventListener("click", () => {
    const selectedCompany = document.getElementById("selectedCompany").dataset.value;
    if (!selectedCompany) {
      alert("Please select a company first!");
      return;
    }
    fetchSentimentData(selectedCompany);
  });
});
