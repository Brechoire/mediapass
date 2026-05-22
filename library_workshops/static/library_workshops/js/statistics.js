// Script pour les graphiques de statistiques des ateliers

function initializeCharts(monthlyData, yearlyData, ageDistribution) {
    console.log('Initialisation des graphiques...');
    console.log('Données mensuelles:', monthlyData);
    console.log('Données annuelles:', yearlyData);
    console.log('Répartition par âge:', ageDistribution);

    // Graphique annuel
    const yearlyCtx = document.getElementById('yearlyChart');
    if (yearlyCtx && yearlyData && yearlyData.length > 0) {
        new Chart(yearlyCtx.getContext('2d'), {
            type: 'bar',
            data: {
                labels: yearlyData.map(item => item.year),
                datasets: [{
                    label: 'Ateliers',
                    data: yearlyData.map(item => item.workshop_count),
                    backgroundColor: '#667eea',
                    borderColor: '#667eea',
                    borderWidth: 1
                }, {
                    label: 'Participants',
                    data: yearlyData.map(item => item.participant_count),
                    backgroundColor: '#28a745',
                    borderColor: '#28a745',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                scales: {
                    x: {
                        display: true,
                        title: {
                            display: true,
                            text: 'Année'
                        }
                    },
                    y: {
                        display: true,
                        title: {
                            display: true,
                            text: 'Nombre'
                        }
                    }
                },
                plugins: {
                    legend: {
                        position: 'top',
                    }
                }
            }
        });
    } else {
        console.log('Pas de données annuelles ou canvas non trouvé');
    }

    // Graphique mensuel
    const monthlyCtx = document.getElementById('monthlyChart');
    if (monthlyCtx && monthlyData && monthlyData.length > 0) {
        new Chart(monthlyCtx.getContext('2d'), {
            type: 'line',
            data: {
                labels: monthlyData.map(item => {
                    const date = new Date(item.month);
                    return date.toLocaleDateString('fr-FR', { month: 'short', year: 'numeric' });
                }),
                datasets: [{
                    label: 'Ateliers',
                    data: monthlyData.map(item => item.workshop_count),
                    borderColor: '#667eea',
                    backgroundColor: 'rgba(102, 126, 234, 0.1)',
                    tension: 0.4,
                    yAxisID: 'y'
                }, {
                    label: 'Participants',
                    data: monthlyData.map(item => item.participant_count),
                    borderColor: '#28a745',
                    backgroundColor: 'rgba(40, 167, 69, 0.1)',
                    tension: 0.4,
                    yAxisID: 'y1'
                }]
            },
            options: {
                responsive: true,
                interaction: {
                    mode: 'index',
                    intersect: false,
                },
                scales: {
                    x: {
                        display: true,
                        title: {
                            display: true,
                            text: 'Mois'
                        }
                    },
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        title: {
                            display: true,
                            text: 'Nombre d\'ateliers'
                        }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        title: {
                            display: true,
                            text: 'Nombre de participants'
                        },
                        grid: {
                            drawOnChartArea: false,
                        },
                    }
                },
                plugins: {
                    legend: {
                        position: 'top',
                    }
                }
            }
        });
    } else {
        console.log('Pas de données mensuelles ou canvas non trouvé');
    }

    // Graphique de répartition par âge
    const ageCtx = document.getElementById('ageChart');
    if (ageCtx && ageDistribution && Object.keys(ageDistribution).length > 0) {
        new Chart(ageCtx.getContext('2d'), {
            type: 'doughnut',
            data: {
                labels: Object.keys(ageDistribution),
                datasets: [{
                    data: Object.values(ageDistribution),
                    backgroundColor: [
                        '#667eea',
                        '#28a745',
                        '#ffc107',
                        '#dc3545',
                        '#17a2b8',
                        '#6f42c1',
                        '#fd7e14'
                    ],
                    borderWidth: 2,
                    borderColor: '#fff'
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        position: 'bottom',
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = ((context.parsed / total) * 100).toFixed(1);
                                return `${context.label}: ${context.parsed} (${percentage}%)`;
                            }
                        }
                    }
                }
            }
        });
    } else {
        console.log('Pas de données de répartition par âge ou canvas non trouvé');
    }
}

// Fonction d'export
function exportData() {
    const data = {
        period: document.querySelector('[data-period]')?.dataset.period || '12_months',
        start_date: document.querySelector('[data-start-date]')?.dataset.startDate || '',
        end_date: document.querySelector('[data-end-date]')?.dataset.endDate || '',
        statistics: {
            total_workshops: parseInt(document.querySelector('[data-total-workshops]')?.dataset.totalWorkshops || '0'),
            total_participants: parseInt(document.querySelector('[data-total-participants]')?.dataset.totalParticipants || '0'),
            avg_fill_rate: parseFloat(document.querySelector('[data-avg-fill-rate]')?.dataset.avgFillRate || '0'),
            overbooking_rate: parseFloat(document.querySelector('[data-overbooking-rate]')?.dataset.overbookingRate || '0')
        }
    };
    
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `statistiques_ateliers_${new Date().toISOString().split('T')[0]}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}
