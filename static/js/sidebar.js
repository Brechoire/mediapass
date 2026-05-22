document.addEventListener('DOMContentLoaded', function() {
    // Toggle submenu
    const menuToggles = document.querySelectorAll('.menu-toggle');
    console.log('Nombre de menus toggle trouvés:', menuToggles.length);
    
    menuToggles.forEach(toggle => {
        toggle.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation(); // Empêcher la propagation du clic
            const menuItem = this.closest('.menu-item');
            console.log('Menu item parent:', menuItem);
            menuItem.classList.toggle('open');
            
            // Fermer les autres menus ouverts
            const siblings = menuItem.parentElement.children;
            Array.from(siblings).forEach(sibling => {
                if (sibling !== menuItem && sibling.classList.contains('open')) {
                    sibling.classList.remove('open');
                }
            });
        });
    });

    // Empêcher la fermeture du menu lors du clic sur les éléments du sous-menu
    const menuSubs = document.querySelectorAll('.menu-sub');
    menuSubs.forEach(menuSub => {
        menuSub.addEventListener('click', function(e) {
            e.stopPropagation();
        });
    });

    // Nouveau off-canvas Tailwind
    const sidebar = document.getElementById('layout-menu');
    const openBtn = document.getElementById('sidebar-open');
    const closeBtn = document.getElementById('sidebar-close');
    const body = document.querySelector('body');

    function openSidebar() {
        if (!sidebar) return;
        sidebar.classList.remove('-translate-x-full');
        body.style.overflow = 'hidden';
    }
    function closeSidebar() {
        if (!sidebar) return;
        sidebar.classList.add('-translate-x-full');
        body.style.overflow = '';
    }

    if (openBtn) openBtn.addEventListener('click', function(e){ e.stopPropagation(); openSidebar(); });
    if (closeBtn) closeBtn.addEventListener('click', function(e){ e.stopPropagation(); closeSidebar(); });

    // Fermer le menu en cliquant à l'extérieur sur mobile
    document.addEventListener('click', function(e) {
        console.log('Click détecté à l\'extérieur du menu');
        // Ne fermer que si on clique en dehors du menu et de ses sous-menus
        if (!e.target.closest('.menu-item')) {
            const openMenus = document.querySelectorAll('.menu-item.open');
            openMenus.forEach(menu => menu.classList.remove('open'));
        }
        
        if (sidebar && !sidebar.contains(e.target) && !e.target.closest('#sidebar-open')) {
            if (window.innerWidth < 1024) {
                closeSidebar();
            }
        }
    });

    // Gérer le redimensionnement de la fenêtre
    let timeout;
    window.addEventListener('resize', function() {
        console.log('Redimensionnement de la fenêtre détecté');
        clearTimeout(timeout);
        timeout = setTimeout(function() {
            console.log('Redimensionnement de la fenêtre confirmé');
            if (window.innerWidth >= 1024) {
                closeSidebar();
            }
        }, 100);
    });
});
