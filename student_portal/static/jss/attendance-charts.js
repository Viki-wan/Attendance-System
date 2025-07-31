// Chart.js Configuration
Chart.defaults.font.family = "'Inter', system-ui, -apple-system, sans-serif";
Chart.defaults.color = '#6c757d';

class AttendanceCharts {
    constructor() {
        console.log('AttendanceCharts constructor called');
        this.monthlyChart = null;
        this.classChart = null;
        this.chartColors = {
            primary: 'rgb(13, 110, 253)',
            success: 'rgb(25, 135, 84)',
            info: 'rgb(13, 202, 240)',
            warning: 'rgb(255, 193, 7)',
            danger: 'rgb(220, 53, 69)'
        };
        this.chartColorsAlpha = {
            primary: 'rgba(13, 110, 253, 0.5)',
            success: 'rgba(25, 135, 84, 0.5)',
            info: 'rgba(13, 202, 240, 0.5)',
            warning: 'rgba(255, 193, 7, 0.5)',
            danger: 'rgba(220, 53, 69, 0.5)'
        };
    }

    initializeCharts() {
        console.log('Initializing charts');
        this.initializeMonthlyChart();
        this.initializeClassChart();
        this.setupDownloadHandlers();
    }

    initializeMonthlyChart() {
        console.log('Initializing monthly chart');
        const monthlyDataStr = document.getElementById('monthlyChartData')?.value;
        console.log('Monthly data string:', monthlyDataStr);
        const monthlyData = monthlyDataStr ? JSON.parse(monthlyDataStr) : [];
        console.log('Parsed monthly data:', monthlyData);
        
        if (monthlyData && monthlyData.length > 0) {
            const monthlyCtx = document.getElementById('monthlyChart')?.getContext('2d');
            if (!monthlyCtx) {
                console.error('Monthly chart canvas not found');
                return;
            }

            console.log('Creating monthly chart');
            this.monthlyChart = new Chart(monthlyCtx, {
                type: 'bar',
                data: {
                    labels: monthlyData.map(item => {
                        const date = new Date(item.month + '-01');
                        return date.toLocaleString('default', { month: 'long', year: 'numeric' });
                    }),
                    datasets: [{
                        label: 'Attendance Rate (%)',
                        data: monthlyData.map(item => 
                            item.total_sessions > 0 
                                ? (item.present_count / item.total_sessions * 100).toFixed(1) 
                                : 0
                        ),
                        backgroundColor: this.chartColorsAlpha.primary,
                        borderColor: this.chartColors.primary,
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        title: {
                            display: true,
                            text: 'Monthly Attendance Trends',
                            font: {
                                size: 16,
                                weight: 'bold'
                            }
                        },
                        legend: {
                            display: false
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    return `Attendance: ${context.raw}%`;
                                }
                            }
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            max: 100,
                            ticks: {
                                callback: value => value + '%'
                            }
                        }
                    }
                }
            });
            console.log('Monthly chart created');
        } else {
            console.log('No monthly data available');
        }
    }

    initializeClassChart() {
        console.log('Initializing class chart');
        const classDataStr = document.getElementById('classChartData')?.value;
        console.log('Class data string:', classDataStr);
        const classData = classDataStr ? JSON.parse(classDataStr) : [];
        console.log('Parsed class data:', classData);
        
        if (classData && classData.length > 0) {
            const classCtx = document.getElementById('classChart')?.getContext('2d');
            if (!classCtx) {
                console.error('Class chart canvas not found');
                return;
            }

            console.log('Creating class chart');
            this.classChart = new Chart(classCtx, {
                type: 'doughnut',
                data: {
                    labels: classData.map(item => item.class_name),
                    datasets: [{
                        data: classData.map(item => 
                            item.total_sessions > 0 
                                ? (item.present_count / item.total_sessions * 100).toFixed(1) 
                                : 0
                        ),
                        backgroundColor: Object.values(this.chartColorsAlpha),
                        borderColor: Object.values(this.chartColors),
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        title: {
                            display: true,
                            text: 'Class-wise Attendance Distribution',
                            font: {
                                size: 16,
                                weight: 'bold'
                            }
                        },
                        legend: {
                            position: 'bottom'
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    const classData = context.chart.data.labels[context.dataIndex];
                                    return `${classData}: ${context.raw}%`;
                                }
                            }
                        }
                    }
                }
            });
            console.log('Class chart created');
        } else {
            console.log('No class data available');
        }
    }

    setupDownloadHandlers() {
        console.log('Setting up download handlers');
        document.getElementById('download-monthly-chart')?.addEventListener('click', (e) => {
            e.preventDefault();
            this.downloadChart('monthlyChart', 'monthly_attendance_trends.png');
        });

        document.getElementById('download-class-chart')?.addEventListener('click', (e) => {
            e.preventDefault();
            this.downloadChart('classChart', 'class_attendance_distribution.png');
        });
    }

    downloadChart(chartId, filename) {
        const canvas = document.getElementById(chartId);
        if (!canvas) {
            console.error(`Canvas not found for chart: ${chartId}`);
            return;
        }

        const link = document.createElement('a');
        link.download = filename;
        link.href = canvas.toDataURL('image/png');
        link.click();
    }
}

// Initialize charts when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM loaded, initializing AttendanceCharts');
    const attendanceCharts = new AttendanceCharts();
    attendanceCharts.initializeCharts();
}); 