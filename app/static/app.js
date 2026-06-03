// Global variables
let allData = null;
let filteredData = null;
let map = null;
let markersLayer = null;
let currentTheme = localStorage.getItem('theme') || 'light';

// Check which page is currently loaded
const isPublicPage = document.getElementById('map') !== null;
const isAdminPage = document.getElementById('admin-entities-list') !== null;

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    
    if (isPublicPage) {
        initPublicPage();
    } else if (isAdminPage) {
        initAdminPage();
    }
});

function initAdminPage() {
    checkAdminAuth();
}

// --- THEME MANAGEMENT ---
function initTheme() {
    document.documentElement.setAttribute('data-theme', currentTheme);
    updateThemeIcon();

    const themeToggleBtn = document.getElementById('theme-toggle');
    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', () => {
            currentTheme = currentTheme === 'light' ? 'dark' : 'light';
            document.documentElement.setAttribute('data-theme', currentTheme);
            localStorage.setItem('theme', currentTheme);
            updateThemeIcon();
        });
    }
}

function updateThemeIcon() {
    const themeIcon = document.getElementById('theme-icon');
    if (themeIcon) {
        if (currentTheme === 'dark') {
            themeIcon.setAttribute('data-lucide', 'sun');
        } else {
            themeIcon.setAttribute('data-lucide', 'moon');
        }
        if (window.lucide) window.lucide.createIcons();
    }
}

// --- TOAST NOTIFICATIONS ---
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;
    
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    let iconName = 'info';
    if (type === 'success') iconName = 'check-circle';
    if (type === 'error') iconName = 'alert-triangle';
    if (type === 'warning') iconName = 'alert-circle';
    
    toast.innerHTML = `<i data-lucide="${iconName}"></i> <span>${message}</span>`;
    container.appendChild(toast);
    if (window.lucide) window.lucide.createIcons();
    
    setTimeout(() => {
        toast.style.animation = 'none';
        toast.style.transition = 'opacity 0.3s ease';
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}


// ==========================================
// PUBLIC VIEW LOGIC (index.html)
// ==========================================

function initPublicPage() {
    // 1. Initialize Map centered on León, Spain
    map = L.map('map', {
        zoomControl: false,
        tap: false
    }).setView([42.598726, -5.568412], 13);
    
    L.control.zoom({ position: 'bottomright' }).addTo(map);

    // Modern light map tiles (CartoDB Positron)
    L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
        subdomains: 'abcd',
        maxZoom: 20
    }).addTo(map);

    markersLayer = L.layerGroup().addTo(map);

    // Add Map Legend
    const legend = L.control({ position: 'bottomleft' });
    legend.onAdd = function (map) {
        const div = L.DomUtil.create('div', 'map-legend');
        div.innerHTML = `
            <h4>Leyenda</h4>
            <div class="legend-item">
                <span class="legend-color legend-entity"></span>
                <span>Entidades Sociales</span>
            </div>
        `;
        return div;
    };
    legend.addTo(map);

    // 2. Fetch Data
    fetch('/api/recursos')
        .then(res => res.json())
        .then(data => {
            allData = data;
            filteredData = { ...data };
            
            // Populate Filters dropdowns with dynamic database catalogs
            populateFiltersDropdowns(data.filters);
            
            // Render Map & Directory Lists
            updateDashboardViews();
            
            // Setup Autocomplete Search Suggestions
            initAutocomplete();
        })
        .catch(err => {
            console.error("Error fetching resources:", err);
            showToast("Error al cargar los recursos de asistencia social.", "error");
        });

    // 3. Setup listeners
    setupPublicListeners();

    // 4. Force map invalidation on window resize
    window.addEventListener('resize', () => {
        if (map) {
            map.invalidateSize();
        }
    });
}

function setupPublicListeners() {
    // Tab switching
    const tabs = document.querySelectorAll('.tab');
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.view-panel').forEach(p => p.classList.remove('active'));
            
            tab.classList.add('active');
            const target = tab.getAttribute('data-tab');
            const targetPanel = document.getElementById(target);
            targetPanel.classList.add('active');
            
            if (target === 'map-view-panel' && map) {
                setTimeout(() => map.invalidateSize(), 100);
            }
        });
    });

    // Filter selectors
    document.getElementById('filter-area').addEventListener('change', filterData);
    document.getElementById('filter-collective').addEventListener('change', filterData);
    document.getElementById('filter-type').addEventListener('change', filterData);
    document.getElementById('filter-titularity').addEventListener('change', filterData);
    
    // Reset Filters
    document.getElementById('btn-reset-filters').addEventListener('click', () => {
        document.getElementById('filter-area').value = "";
        document.getElementById('filter-collective').value = "";
        document.getElementById('filter-type').value = "";
        document.getElementById('filter-titularity').value = "";
        document.getElementById('main-search').value = "";
        filterData();
    });

    // Search input instant search
    document.getElementById('main-search').addEventListener('input', () => {
        filterData();
    });
}

function populateFiltersDropdowns(filters) {
    const areaSel = document.getElementById('filter-area');
    const collectiveSel = document.getElementById('filter-collective');
    const typeSel = document.getElementById('filter-type');
    
    // Clear old options except first
    areaSel.innerHTML = '<option value="">Todas las Áreas</option>';
    collectiveSel.innerHTML = '<option value="">Todos los Colectivos</option>';
    typeSel.innerHTML = '<option value="">Todos los Tipos</option>';

    filters.areas.forEach(a => {
        areaSel.innerHTML += `<option value="${a.id_area}">${a.nombre_area}</option>`;
    });
    filters.collectives.forEach(c => {
        collectiveSel.innerHTML += `<option value="${c.id_colectivo}">${c.nombre_colectivo}</option>`;
    });
    filters.service_types.forEach(t => {
        typeSel.innerHTML += `<option value="${t.id_tipo_servicio}">${t.nombre_tipo_servicio}</option>`;
    });
}

function filterData() {
    if (!allData) return;

    const searchVal = document.getElementById('main-search').value.toLowerCase().trim();
    const areaVal = document.getElementById('filter-area').value;
    const collectiveVal = document.getElementById('filter-collective').value;
    const typeVal = document.getElementById('filter-type').value;
    const titularityVal = document.getElementById('filter-titularity').value;

    // Filter Entidades and their services
    let filteredEntities = allData.entidades.filter(ent => {
        // Area check (by ID)
        if (areaVal && String(ent.id_area) !== areaVal) return false;
        // Collective check (by ID)
        if (collectiveVal && String(ent.id_colectivo) !== collectiveVal) return false;
        // Titularity check
        if (titularityVal && ent.titularidad !== titularityVal) return false;
        
        // Service type check (does it offer at least one service of this type?)
        if (typeVal) {
            const hasType = ent.servicios.some(s => String(s.id_tipo_servicio) === typeVal);
            if (!hasType) return false;
        }

        // Search text check
        if (searchVal) {
            const matchName = ent.nombre.toLowerCase().includes(searchVal);
            const matchAddress = (ent.direccion || '').toLowerCase().includes(searchVal);
            const matchServices = ent.servicios.some(s => 
                s.nombre.toLowerCase().includes(searchVal) || 
                (s.descripcion_corta || '').toLowerCase().includes(searchVal) ||
                (s.descripcion_larga || '').toLowerCase().includes(searchVal)
            );
            return matchName || matchAddress || matchServices;
        }

        return true;
    });

    filteredData = {
        entidades: filteredEntities,
        servicios_basicos: []
    };

    updateDashboardViews();
}

function updateDashboardViews() {
    if (!filteredData) return;

    // 1. Update stats counter
    const totalCount = filteredData.entidades.length;
    document.getElementById('stats-counter').innerHTML = `${totalCount} recursos encontrados`;

    // 2. Render Markers on Map
    renderMapMarkers();

    // 3. Render Directory Cards List
    renderDirectoryView();

    // 4. Invalidate size if map view is active to prevent rendering bugs
    const mapPanel = document.getElementById('map-view-panel');
    if (mapPanel && mapPanel.classList.contains('active') && map) {
        setTimeout(() => map.invalidateSize(), 50);
    }
}

function renderMapMarkers() {
    if (!map || !markersLayer) return;
    markersLayer.clearLayers();

    filteredData.entidades.forEach(ent => {
        const lat = ent.latitude !== undefined ? ent.latitude : ent.Latitude;
        const lon = ent.longitude !== undefined ? ent.longitude : ent.Longitude;
        if (lat && lon) {
            const customIcon = L.divIcon({
                html: `<div class="custom-div-icon"><div class="marker-pin"></div></div>`,
                className: 'custom-marker',
                iconSize: [30, 42],
                iconAnchor: [15, 42]
            });

            const marker = L.marker([lat, lon], { icon: customIcon });
            
            const popupContent = `
                <div style="font-family: var(--font-primary); padding: 5px; max-width: 250px;">
                    <h4 style="font-weight:700; margin-bottom:4px;">${ent.nombre}</h4>
                    <p style="font-size:0.8rem; color:var(--text-secondary); margin-bottom:8px;">${ent.direccion || ''}</p>
                    <span class="tag tag-area" style="font-size:0.65rem;">${ent.area || 'Social'}</span>
                    <a onclick="openEntityDetails(${ent.id})" style="display:block; margin-top:8px; font-size:0.8rem; color:var(--primary); font-weight:600; cursor:pointer;">Ver más detalles</a>
                </div>
            `;
            marker.bindPopup(popupContent);
            markersLayer.addLayer(marker);
        }
    });
}

function renderDirectoryView() {
    const container = document.getElementById('directory-container');
    if (!container) return;
    container.innerHTML = "";

    if (filteredData.entidades.length === 0) {
        container.innerHTML = `
            <div style="grid-column: 1/-1; text-align:center; padding: 48px; color: var(--text-secondary);">
                <i data-lucide="info" style="width:48px; height:48px; margin:0 auto 12px; color:var(--text-muted)"></i>
                <p>No se encontraron entidades sociales con los filtros actuales.</p>
            </div>
        `;
        if (window.lucide) window.lucide.createIcons();
        return;
    }

    filteredData.entidades.forEach(ent => {
        const card = document.createElement('div');
        card.className = 'resource-card';
        card.onclick = () => openEntityDetails(ent.id);

        let tagsHTML = `<span class="tag tag-area">${ent.area}</span>`;
        if (ent.colectivo && ent.colectivo !== "Sin especificar") {
            tagsHTML += `<span class="tag tag-collective">${ent.colectivo}</span>`;
        }
        if (ent.titularidad) {
            tagsHTML += `<span class="tag tag-type">${ent.titularidad}</span>`;
        }

        card.innerHTML = `
            <div class="card-tags">${tagsHTML}</div>
            <h3 class="card-title">${ent.nombre}</h3>
            <div class="card-info">
                <div class="info-item"><i data-lucide="map-pin" style="width:14px;"></i> <span>${ent.direccion || 'Sin dirección'}</span></div>
                ${ent.telefono ? `<div class="info-item"><i data-lucide="phone" style="width:14px;"></i> <span>${ent.telefono}</span></div>` : ''}
                <div class="info-item"><i data-lucide="grid" style="width:14px;"></i> <span>${ent.servicios.length} servicios que ofrece</span></div>
            </div>
        `;
        container.appendChild(card);
    });
    if (window.lucide) window.lucide.createIcons();
}

// --- Autocomplete Search Setup ---
function initAutocomplete() {
    const input = document.getElementById('main-search');
    const list = document.getElementById('search-suggestions');
    if (!input || !list) return;

    // Close suggestions list if click outside
    document.addEventListener('click', (e) => {
        if (e.target !== input && e.target !== list) {
            list.style.display = 'none';
        }
    });

    input.addEventListener('focus', showSuggestions);
    input.addEventListener('input', showSuggestions);

    function showSuggestions() {
        const val = input.value.toLowerCase().trim();
        if (!val || !allData) {
            list.style.display = 'none';
            return;
        }

        list.innerHTML = "";
        let items = [];

        // Match Entities
        allData.entidades.forEach(ent => {
            const lat = ent.latitude !== undefined ? ent.latitude : ent.Latitude;
            const lon = ent.longitude !== undefined ? ent.longitude : ent.Longitude;
            if (ent.nombre.toLowerCase().includes(val)) {
                items.push({
                    type: 'entity',
                    id: ent.id,
                    title: ent.nombre,
                    subtitle: `${ent.direccion || ''} (Entidad)`,
                    lat: lat,
                    lon: lon
                });
            }
            // Match Services
            ent.servicios.forEach(s => {
                if (s.nombre.toLowerCase().includes(val)) {
                    items.push({
                        type: 'entity',
                        id: ent.id,
                        title: s.nombre,
                        subtitle: `Ofrecido por: ${ent.nombre}`,
                        lat: lat,
                        lon: lon
                    });
                }
            });
        });

        // Limit suggestions to 6
        const sliced = items.slice(0, 6);
        if (sliced.length === 0) {
            list.style.display = 'none';
            return;
        }

        sliced.forEach(item => {
            const div = document.createElement('div');
            div.className = 'suggestion-item';
            div.innerHTML = `
                <div class="suggestion-title">${item.title}</div>
                <div class="suggestion-subtitle">${item.subtitle}</div>
            `;
            div.onclick = () => {
                input.value = item.title;
                list.style.display = 'none';
                
                // Focus on map coordinates if present
                if (item.lat && item.lon && map) {
                    map.setView([item.lat, item.lon], 16);
                }
                
                openEntityDetails(item.id);
            };
            list.appendChild(div);
        });

        list.style.display = 'block';
    }
}

// --- Dynamic Modal Display ---
function openEntityDetails(id) {
    if (!allData) return;
    const ent = allData.entidades.find(e => e.id === id);
    if (!ent) return;

    document.getElementById('modal-entity-name').innerText = ent.nombre;
    document.getElementById('modal-entity-type').innerText = ent.tipo_entidad || 'Entidad de Asistencia Social';

    // Contact Panel
    const contactPanel = document.getElementById('modal-entity-contact');
    contactPanel.innerHTML = `
        ${ent.direccion ? `<div class="info-item"><i data-lucide="map-pin" style="width:16px;"></i> <span><strong>Dirección:</strong> ${ent.direccion} (${ent.cp || ''})</span></div>` : ''}
        ${ent.telefono ? `<div class="info-item"><i data-lucide="phone" style="width:16px;"></i> <span><strong>Teléfono 1:</strong> ${ent.telefono}</span></div>` : ''}
        ${ent.telefono2 ? `<div class="info-item"><i data-lucide="phone" style="width:16px;"></i> <span><strong>Teléfono 2:</strong> ${ent.telefono2}</span></div>` : ''}
        ${ent.email ? `<div class="info-item"><i data-lucide="mail" style="width:16px;"></i> <span><strong>Email:</strong> <a href="mailto:${ent.email}">${ent.email}</a></span></div>` : ''}
        ${ent.web ? `<div class="info-item"><i data-lucide="globe" style="width:16px;"></i> <span><strong>Web:</strong> <a href="http://${ent.web}" target="_blank">${ent.web}</a></span></div>` : ''}
    `;

    // Classification Panel
    const classPanel = document.getElementById('modal-entity-classification');
    classPanel.innerHTML = `
        <div class="info-item"><i data-lucide="layers" style="width:16px;"></i> <span><strong>Área:</strong> ${ent.area}</span></div>
        <div class="info-item"><i data-lucide="users" style="width:16px;"></i> <span><strong>Colectivo:</strong> ${ent.colectivo}</span></div>
        <div class="info-item"><i data-lucide="shield" style="width:16px;"></i> <span><strong>Titularidad:</strong> ${ent.titularidad || 'No especificada'}</span></div>
        ${ent.ceas ? `<div class="info-item"><i data-lucide="home" style="width:16px;"></i> <span><strong>CEAS Vinculado:</strong> ${ent.ceas}</span></div>` : ''}
    `;

    // Services list
    const servicesList = document.getElementById('modal-services-list');
    servicesList.innerHTML = "";

    if (ent.servicios.length === 0) {
        servicesList.innerHTML = `<p style="font-size:0.9rem; color:var(--text-secondary); text-align:center; padding:12px;">Esta entidad no tiene cargados servicios o prestaciones detallados.</p>`;
    } else {
        ent.servicios.forEach(s => {
            const sCard = document.createElement('div');
            sCard.className = 'service-item-card';

            let docsHTML = "";
            if (s.documentacion && s.documentacion.length > 0) {
                docsHTML = `
                    <div style="margin-top: 12px;">
                        <span class="meta-label">Documentación requerida</span>
                        <div class="docs-list" style="margin-top:6px;">
                            ${s.documentacion.map(d => `<span class="doc-pill"><i data-lucide="file-text" style="width:12px; color:var(--primary);"></i> ${d}</span>`).join('')}
                        </div>
                    </div>
                `;
            }

            sCard.innerHTML = `
                <div class="service-name">
                    <span>${s.nombre}</span>
                    <span class="service-type-badge">${s.tipo_registro.toUpperCase()}</span>
                </div>
                ${s.descripcion_larga ? `<p class="service-desc">${s.descripcion_larga}</p>` : (s.descripcion_corta ? `<p class="service-desc">${s.descripcion_corta}</p>` : '')}
                
                <div class="service-meta-grid">
                    <div class="meta-field">
                        <span class="meta-label">Tipo</span>
                        <span class="meta-value">${s.tipo_servicio}</span>
                    </div>
                    <div class="meta-field">
                        <span class="meta-label">Cita Previa</span>
                        <span class="meta-value">${s.cita_previa || 'No requerido'}</span>
                    </div>
                    <div class="meta-field">
                        <span class="meta-label">Plazas</span>
                        <span class="meta-value">${s.plazas || 'Sin límite'}</span>
                    </div>
                    <div class="meta-field">
                        <span class="meta-label">Aportación (Coste)</span>
                        <span class="meta-value">${s.aportacion_beneficiario || 'Gratuito'}</span>
                    </div>
                    ${s.horario ? `
                    <div class="meta-field" style="grid-column: span 2;">
                        <span class="meta-label">Horario</span>
                        <span class="meta-value">${s.horario}</span>
                    </div>` : ''}
                    ${s.condiciones_admision ? `
                    <div class="meta-field" style="grid-column: span 2;">
                        <span class="meta-label">Condiciones de Admisión</span>
                        <span class="meta-value">${s.condiciones_admision}</span>
                    </div>` : ''}
                </div>
                ${docsHTML}
            `;
            servicesList.appendChild(sCard);
        });
    }

    document.getElementById('detail-modal').classList.add('active');
    if (window.lucide) window.lucide.createIcons();
}

function closeModal() {
    document.getElementById('detail-modal').classList.remove('active');
}


// ==========================================
// ADMIN DASHBOARD LOGIC (admin.html)
// ==========================================

function checkAdminAuth() {
    fetch('/api/auth/check')
        .then(res => res.json())
        .then(data => {
            if (!data.authenticated) {
                showToast("Acceso no autorizado. Redirigiendo...", "warning");
                setTimeout(() => {
                    window.location.href = 'login.html';
                }, 1000);
            } else {
                document.getElementById('user-display').innerText = `Admin: ${data.user.username}`;
                loadAdminData();
            }
        })
        .catch(() => {
            window.location.href = 'login.html';
        });
}

function handleLogout() {
    fetch('/api/auth/logout', { method: 'POST' })
        .then(() => {
            showToast("Sesión cerrada", "success");
            setTimeout(() => {
                window.location.href = 'login.html';
            }, 500);
        });
}

function loadAdminData() {
    fetch('/api/recursos')
        .then(res => res.json())
        .then(data => {
            allData = data;
            
            // Populate selector categories inside forms using normalized catalog tables
            populateFormDropdowns(data.filters);
            
            // Render entities list
            renderAdminEntities();
        })
        .catch(() => {
            showToast("Error al cargar datos del panel", "error");
        });
}

function populateFormDropdowns(filters) {
    const areaSel = document.getElementById('ent-area');
    const collectiveSel = document.getElementById('ent-colectivo');
    const typeSel = document.getElementById('ser-tipo-servicio');

    // Load options mapping to IDs
    areaSel.innerHTML = filters.areas.map(a => `<option value="${a.id_area}">${a.nombre_area}</option>`).join('');
    collectiveSel.innerHTML = filters.collectives.map(c => `<option value="${c.id_colectivo}">${c.nombre_colectivo}</option>`).join('');
    typeSel.innerHTML = filters.service_types.map(t => `<option value="${t.id_tipo_servicio}">${t.nombre_tipo_servicio}</option>`).join('');
}

function renderAdminEntities() {
    const container = document.getElementById('admin-entities-list');
    if (!container) return;
    container.innerHTML = "";

    const searchVal = document.getElementById('admin-search').value.toLowerCase().trim();
    
    let list = allData.entidades;
    if (searchVal) {
        list = list.filter(e => 
            e.nombre.toLowerCase().includes(searchVal) || 
            (e.direccion || '').toLowerCase().includes(searchVal)
        );
    }

    if (list.length === 0) {
        container.innerHTML = `<div style="text-align:center; padding: 48px; color: var(--text-secondary);">No se encontraron entidades.</div>`;
        return;
    }

    list.forEach(ent => {
        const card = document.createElement('div');
        card.className = 'admin-entity-card';
        card.id = `admin-ent-card-${ent.id}`;

        // Create services row
        let servicesRows = "";
        if (ent.servicios.length === 0) {
            servicesRows = `<p style="font-size:0.85rem; color:var(--text-secondary); text-align:center; padding:12px;">No hay servicios creados para esta entidad.</p>`;
        } else {
            ent.servicios.forEach(s => {
                servicesRows += `
                    <div class="admin-service-row">
                        <div>
                            <span style="font-weight:600; font-size:0.9rem;">${s.nombre}</span>
                            <span class="service-type-badge" style="margin-left:8px;">${s.tipo_registro.toUpperCase()}</span>
                            <p style="font-size:0.75rem; color:var(--text-secondary); margin-top:2px;">${s.tipo_servicio} | ${s.plazas || 'Sin límite'} plazas</p>
                        </div>
                        <div class="admin-entity-actions">
                            <button class="btn btn-secondary" onclick="openServiceModal(${ent.id}, ${s.id}, event)">
                                <i data-lucide="edit-3" style="width:14px;"></i> Editar
                            </button>
                            <button class="btn btn-danger" onclick="deleteService(${s.id}, event)">
                                <i data-lucide="trash-2" style="width:14px;"></i> Borrar
                            </button>
                        </div>
                    </div>
                `;
            });
        }

        card.innerHTML = `
            <div class="admin-entity-header" onclick="toggleEntityCollapse(${ent.id})">
                <div class="admin-entity-title">
                    <i data-lucide="chevron-right" class="collapse-icon" id="collapse-icon-${ent.id}"></i>
                    <div>
                        <strong style="font-size:1.05rem;">${ent.nombre}</strong>
                        <span class="tag tag-area" style="margin-left:12px; font-size:0.7rem;">${ent.area}</span>
                    </div>
                </div>
                <div class="admin-entity-actions">
                    <button class="btn btn-primary" style="padding: 6px 12px;" onclick="openServiceModal(${ent.id}, null, event)">
                        <i data-lucide="plus" style="width:14px;"></i> Añadir Servicio
                    </button>
                    <button class="btn btn-secondary" style="padding: 6px 12px;" onclick="openEntityModal(${ent.id}, event)">
                        <i data-lucide="edit-3" style="width:14px;"></i> Editar
                    </button>
                    <button class="btn btn-danger" style="padding: 6px 12px; background-color:#ef4444;" onclick="deleteEntity(${ent.id}, event)">
                        <i data-lucide="trash-2" style="width:14px;"></i> Borrar
                    </button>
                </div>
            </div>
            <div class="admin-entity-body">
                <div style="font-size: 0.9rem; margin-bottom: 20px; display: grid; grid-template-columns: 1fr 1fr; gap:16px;">
                    <div>
                        <p><strong>Dirección:</strong> ${ent.direccion || ''} (${ent.cp || ''})</p>
                        <p><strong>Contacto:</strong> ${ent.telefono || ''} ${ent.telefono2 ? '/ ' + ent.telefono2 : ''} | ${ent.email || ''}</p>
                        <p><strong>Web:</strong> ${ent.web || ''}</p>
                    </div>
                    <div>
                        <p><strong>Colectivo:</strong> ${ent.colectivo}</p>
                        <p><strong>Titularidad:</strong> ${ent.titularidad || ''}</p>
                        <p><strong>CEAS Zona:</strong> ${ent.ceas || 'No especificado'}</p>
                    </div>
                </div>
                
                <h4 style="font-size: 0.9rem; font-weight:700; border-bottom: 1px solid var(--border-color); padding-bottom:6px;">Servicios Asignados</h4>
                <div class="admin-services-list">
                    ${servicesRows}
                </div>
            </div>
        `;
        container.appendChild(card);
    });
    if (window.lucide) window.lucide.createIcons();
}

function toggleEntityCollapse(id) {
    const card = document.getElementById(`admin-ent-card-${id}`);
    const icon = document.getElementById(`collapse-icon-${id}`);
    
    if (card.classList.contains('expanded')) {
        card.classList.remove('expanded');
        icon.style.transform = 'rotate(0deg)';
    } else {
        card.classList.add('expanded');
        icon.style.transform = 'rotate(90deg)';
    }
}

// --- ENTITY CRUD HANDLERS ---
function openEntityModal(id = null, event = null) {
    if (event) event.stopPropagation();

    document.getElementById('entity-form').reset();
    
    if (id) {
        const ent = allData.entidades.find(e => e.id === id);
        if (!ent) return;
        
        document.getElementById('entity-modal-title').innerText = "Editar Entidad";
        document.getElementById('entity-id').value = ent.id;
        document.getElementById('ent-nombre').value = ent.nombre;
        document.getElementById('ent-tipo').value = ent.tipo_entidad || '';
        document.getElementById('ent-titularidad').value = ent.titularidad || 'Pública';
        document.getElementById('ent-direccion').value = ent.direccion || '';
        document.getElementById('ent-cp').value = ent.cp || '';
        document.getElementById('ent-localidad').value = ent.localidad || 'LEÓN';
        document.getElementById('ent-latitud').value = (ent.latitude !== undefined ? ent.latitude : ent.Latitude) || '';
        document.getElementById('ent-longitud').value = (ent.longitude !== undefined ? ent.longitude : ent.Longitude) || '';
        document.getElementById('ent-telefono').value = ent.telefono || '';
        document.getElementById('ent-telefono2').value = ent.telefono2 || '';
        document.getElementById('ent-email').value = ent.email || '';
        document.getElementById('ent-web').value = ent.web || '';
        document.getElementById('ent-ceas').value = ent.ceas || '';
        
        // Map to IDs
        document.getElementById('ent-area').value = ent.id_area || '';
        document.getElementById('ent-colectivo').value = ent.id_colectivo || '';
    } else {
        document.getElementById('entity-modal-title').innerText = "Crear Nueva Entidad";
        document.getElementById('entity-id').value = "";
    }
    
    document.getElementById('entity-modal').classList.add('active');
}

function closeEntityModal() {
    document.getElementById('entity-modal').classList.remove('active');
}

function saveEntity(event) {
    event.preventDefault();
    
    const id = document.getElementById('entity-id').value;
    const body = {
        nombre: document.getElementById('ent-nombre').value,
        tipo_entidad: document.getElementById('ent-tipo').value,
        titularidad: document.getElementById('ent-titularidad').value,
        direccion: document.getElementById('ent-direccion').value,
        cp: document.getElementById('ent-cp').value,
        localidad: document.getElementById('ent-localidad').value,
        telefono: document.getElementById('ent-telefono').value,
        telefono2: document.getElementById('ent-telefono2').value,
        email: document.getElementById('ent-email').value,
        web: document.getElementById('ent-web').value,
        ceas: document.getElementById('ent-ceas').value,
        area: document.getElementById('ent-area').value, // Relational ID
        colectivo: document.getElementById('ent-colectivo').value, // Relational ID
        latitude: document.getElementById('ent-latitud').value ? parseFloat(document.getElementById('ent-latitud').value) : null,
        longitude: document.getElementById('ent-longitud').value ? parseFloat(document.getElementById('ent-longitud').value) : null
    };

    const method = id ? 'PUT' : 'POST';
    const url = id ? `/api/entidades/${id}` : '/api/entidades';

    fetch(url, {
        method: method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
    })
    .then(async res => {
        const data = await res.json();
        if (res.ok) {
            showToast("Entidad guardada con éxito", "success");
            closeEntityModal();
            loadAdminData();
        } else {
            showToast(data.error || "Error al guardar entidad", "error");
        }
    })
    .catch(() => showToast("Error de conexión", "error"));
}

function deleteEntity(id, event) {
    event.stopPropagation();
    if (!confirm("¿Está seguro de que desea eliminar esta entidad? Todos sus servicios asociados también serán eliminados.")) return;

    fetch(`/api/entidades/${id}`, { method: 'DELETE' })
        .then(async res => {
            const data = await res.json();
            if (res.ok) {
                showToast("Entidad eliminada", "success");
                loadAdminData();
            } else {
                showToast(data.error || "Error al eliminar", "error");
            }
        });
}


// --- SERVICE CRUD HANDLERS ---
function openServiceModal(entId, sId = null, event = null) {
    if (event) event.stopPropagation();

    document.getElementById('service-form').reset();
    document.getElementById('service-entity-id').value = entId;
    
    if (sId) {
        const ent = allData.entidades.find(e => e.id === entId);
        const s = ent.servicios.find(sv => sv.id === sId);
        
        document.getElementById('service-modal-title').innerText = "Editar Servicio";
        document.getElementById('service-id').value = s.id;
        document.getElementById('ser-nombre').value = s.nombre;
        document.getElementById('ser-tipo-registro').value = s.tipo_registro;
        document.getElementById('ser-tipo-servicio').value = s.id_tipo_servicio || '';
        document.getElementById('ser-desc-corta').value = s.descripcion_corta || '';
        document.getElementById('ser-desc-larga').value = s.descripcion_larga || '';
        document.getElementById('ser-plazas').value = s.plazas || '';
        document.getElementById('ser-cita').value = s.cita_previa || '';
        document.getElementById('ser-horario').value = s.horario || '';
        document.getElementById('ser-aportacion').value = s.aportacion_beneficiario || '';
        document.getElementById('ser-condiciones').value = s.condiciones_admision || '';
        document.getElementById('ser-finalidad').value = s.finalidad || '';
        document.getElementById('ser-documentos').value = (s.documentacion || []).join('\n');
    } else {
        document.getElementById('service-modal-title').innerText = "Añadir Servicio";
        document.getElementById('service-id').value = "";
    }

    document.getElementById('service-modal').classList.add('active');
}

function closeServiceModal() {
    document.getElementById('service-modal').classList.remove('active');
}

function saveService(event) {
    event.preventDefault();
    
    const id = document.getElementById('service-id').value;
    const entId = document.getElementById('service-entity-id').value;
    const docText = document.getElementById('ser-documentos').value;
    const docs = docText.split('\n').map(d => d.trim()).filter(d => d.length > 0);

    const body = {
        entidad_id: parseInt(entId),
        nombre: document.getElementById('ser-nombre').value,
        tipo_registro: document.getElementById('ser-tipo-registro').value,
        tipo_servicio: document.getElementById('ser-tipo-servicio').value, // Relational ID
        descripcion_corta: document.getElementById('ser-desc-corta').value,
        descripcion_larga: document.getElementById('ser-desc-larga').value,
        plazas: document.getElementById('ser-plazas').value,
        cita_previa: document.getElementById('ser-cita').value,
        horario: document.getElementById('ser-horario').value,
        aportacion_beneficiario: document.getElementById('ser-aportacion').value,
        condiciones_admision: document.getElementById('ser-condiciones').value,
        finalidad: document.getElementById('ser-finalidad').value,
        documentacion: docs
    };

    const method = id ? 'PUT' : 'POST';
    const url = id ? `/api/servicios/${id}` : '/api/servicios';

    fetch(url, {
        method: method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
    })
    .then(async res => {
        const data = await res.json();
        if (res.ok) {
            showToast("Servicio guardado con éxito", "success");
            closeServiceModal();
            loadAdminData();
        } else {
            showToast(data.error || "Error al guardar servicio", "error");
        }
    })
    .catch(() => showToast("Error de conexión", "error"));
}

function deleteService(sId, event) {
    event.stopPropagation();
    if (!confirm("¿Está seguro de que desea eliminar este servicio?")) return;

    fetch(`/api/servicios/${sId}`, { method: 'DELETE' })
        .then(async res => {
            const data = await res.json();
            if (res.ok) {
                showToast("Servicio eliminado", "success");
                loadAdminData();
            } else {
                showToast(data.error || "Error al eliminar", "error");
            }
        });
}


// --- ADMIN USER ACTIONS ---
function loadAdminUsersList() {
    fetch('/api/users')
        .then(res => res.json())
        .then(users => {
            const tbody = document.getElementById('admin-users-list');
            tbody.innerHTML = "";
            
            users.forEach(u => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td style="font-weight:600;">${u.username}</td>
                    <td>${u.email}</td>
                    <td>${u.created_at}</td>
                    <td style="text-align:right;">
                        <button class="btn btn-danger" style="padding: 6px 12px;" onclick="deleteAdminUser(${u.id})">
                            <i data-lucide="user-x" style="width:14px;"></i> Eliminar
                        </button>
                    </td>
                `;
                tbody.appendChild(tr);
            });
            if (window.lucide) window.lucide.createIcons();
        });
}

function openUserModal() {
    document.getElementById('user-form').reset();
    document.getElementById('user-modal').classList.add('active');
}

function closeUserModal() {
    document.getElementById('user-modal').classList.remove('active');
}

function saveUser(event) {
    event.preventDefault();
    const username = document.getElementById('user-name').value;
    const email = document.getElementById('user-email').value;
    const password = document.getElementById('user-password').value;

    fetch('/api/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, email, password })
    })
    .then(async res => {
        const data = await res.json();
        if (res.ok) {
            showToast("Administrador creado correctamente", "success");
            closeUserModal();
            loadAdminUsersList();
        } else {
            showToast(data.error || "Error al crear administrador", "error");
        }
    })
    .catch(() => showToast("Error de red", "error"));
}

function deleteAdminUser(id) {
    if (!confirm("¿Está seguro de que desea eliminar a este administrador?")) return;

    fetch(`/api/users/${id}`, { method: 'DELETE' })
        .then(async res => {
            const data = await res.json();
            if (res.ok) {
                showToast("Administrador eliminado", "success");
                loadAdminUsersList();
            } else {
                showToast(data.error || "Error al eliminar", "error");
            }
        });
}


// --- PASSWORD MODALS ---
function openChangePasswordModal() {
    document.getElementById('password-form').reset();
    document.getElementById('password-modal').classList.add('active');
}

function closeChangePasswordModal() {
    document.getElementById('password-modal').classList.remove('active');
}

function saveNewPassword(event) {
    event.preventDefault();
    const old_password = document.getElementById('pwd-old').value;
    const new_password = document.getElementById('pwd-new').value;
    const confirm = document.getElementById('pwd-confirm').value;

    if (new_password !== confirm) {
        showToast("Las contraseñas no coinciden", "error");
        return;
    }

    fetch('/api/users/change-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ old_password, new_password })
    })
    .then(async res => {
        const data = await res.json();
        if (res.ok) {
            showToast("Contraseña actualizada con éxito", "success");
            closeChangePasswordModal();
        } else {
            showToast(data.error || "Error al cambiar contraseña", "error");
        }
    })
    .catch(() => showToast("Error al enviar", "error"));
}
