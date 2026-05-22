document.addEventListener('DOMContentLoaded', function() {
    // Graphique en donut pour la répartition des ateliers
    const workshopDistributionCtx = document.getElementById('workshopDistribution');
    if (workshopDistributionCtx) {
        new Chart(workshopDistributionCtx, {
            type: 'doughnut',
            data: {
                labels: ['Ateliers standards', 'Accueils de classe'],
                datasets: [{
                    data: [
                        workshopDistributionCtx.dataset.standardWorkshops,
                        workshopDistributionCtx.dataset.classWorkshops
                    ],
                    backgroundColor: ['#696cff', '#03c3ec'],
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        position: 'bottom',
                    },
                    title: {
                        display: true,
                        text: 'Répartition des types d\'ateliers'
                    }
                }
            }
        });
    }

    // Graphique en barres pour les ateliers par lieu
    const workshopsByLocationCtx = document.getElementById('workshopsByLocation');
    if (workshopsByLocationCtx) {
        const locationData = JSON.parse(workshopsByLocationCtx.dataset.locations);
        new Chart(workshopsByLocationCtx, {
            type: 'bar',
            data: {
                labels: locationData.map(item => item.name),
                datasets: [{
                    label: 'Nombre d\'ateliers',
                    data: locationData.map(item => item.count),
                    backgroundColor: '#696cff',
                    borderWidth: 1
                }, {
                    label: 'Participants inscrits',
                    data: locationData.map(item => item.registered),
                    backgroundColor: '#03c3ec',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: true
                    }
                },
                plugins: {
                    legend: {
                        position: 'bottom',
                    },
                    title: {
                        display: true,
                        text: 'Ateliers et participants par lieu'
                    }
                }
            }
        });
    }

    // Graphique en ligne pour le taux de conversion
    const conversionRateCtx = document.getElementById('conversionRate');
    if (conversionRateCtx) {
        new Chart(conversionRateCtx, {
            type: 'line',
            data: {
                labels: ['Inscrits', 'Présents'],
                datasets: [{
                    label: 'Nombre de participants',
                    data: [
                        conversionRateCtx.dataset.registered,
                        conversionRateCtx.dataset.attended
                    ],
                    borderColor: '#696cff',
                    tension: 0.1
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        position: 'bottom',
                    },
                    title: {
                        display: true,
                        text: 'Taux de conversion inscription → participation'
                    }
                }
            }
        });
    }
});
