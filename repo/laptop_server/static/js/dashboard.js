document.addEventListener('DOMContentLoaded', () => {
    // Elements
    const statusIndicator = document.getElementById('connection-status');
    const statusText = statusIndicator.querySelector('.status-text');
    const liveFeed = document.getElementById('live-feed');
    const noFeedOverlay = document.getElementById('no-feed-overlay');
    const deviceIdBadge = document.getElementById('device-id-badge');
    const conveyorStatus = document.getElementById('conveyor-status');
    
    const fruitIcon = document.getElementById('fruit-icon');
    const currentLabel = document.getElementById('current-label');
    const confidenceBar = document.getElementById('confidence-bar');
    const confidenceText = document.getElementById('confidence-text');
    
    const metaFrameId = document.getElementById('meta-frame-id');
    const metaLatency = document.getElementById('meta-latency');
    const metaTime = document.getElementById('meta-time');
    
    const countCam = document.getElementById('count-cam');
    const countChanh = document.getElementById('count-chanh');
    const countQuyt = document.getElementById('count-quyt');
    const countTotal = document.getElementById('count-total');
    
    const historyBody = document.getElementById('history-body');
    const btnClearHistory = document.getElementById('btn-clear-history');
    
    const modal = document.getElementById('image-modal');
    const modalImg = document.getElementById('modal-img');
    const modalCaption = document.getElementById('modal-caption');
    const modalClose = document.querySelector('.modal-close');

    // State
    let socket = null;
    let stats = { cam: 0, chanh: 0, quyt: 0, total: 0 };
    let history = [];
    const MAX_HISTORY = 50;
    const COMMAND_DEBOUNCE_MS = 300;
    let lastCommandAt = 0;

    const fruitConfig = {
        'cam': { name: 'CAM (Orange)', icon: '🍊', color: '#f97316' },
        'chanh': { name: 'CHANH (Lemon)', icon: '🍋', color: '#eab308' },
        'quyt': { name: 'QUÝT (Mandarin)', icon: '🟠', color: '#fb923c' },
        'unknown': { name: 'Không xác định', icon: '❓', color: '#6b7280' }
    };

    const manualKeyMap = {
        '1': 'cam',
        '2': 'chanh',
        '3': 'quyt',
        '4': 'unknown',
        'ArrowLeft': 'cam',
        'ArrowDown': 'chanh',
        'ArrowRight': 'quyt',
        'ArrowUp': 'unknown'
    };

    // WebSocket Initialization
    function connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/dashboard`;
        
        console.log(`Connecting to ${wsUrl}...`);
        socket = new WebSocket(wsUrl);

        socket.onopen = () => {
            console.log('Connected to Server');
            statusIndicator.classList.add('connected');
            statusText.textContent = 'CONNECTED';
        };

        socket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                updateUI(data);
            } catch (err) {
                console.error('Error processing message:', err);
            }
        };

        socket.onclose = () => {
            console.log('Disconnected from Server');
            statusIndicator.classList.remove('connected');
            statusText.textContent = 'DISCONNECTED';
            // Auto-reconnect after 3 seconds
            setTimeout(connect, 3000);
        };

        socket.onerror = (err) => {
            console.error('WebSocket Error:', err);
            socket.close();
        };
    }

    // UI Updates
    function updateUI(data) {
        const { device_id, frame_id, timestamp, label, confidence, conveyor_status, image } = data;
        
        if (!label) {
            console.warn('Received data without label:', data);
            return;
        }

        const safeLabel = label.toString().toLowerCase();

        // Hide overlay on first image
        if (image) {
            noFeedOverlay.style.display = 'none';
            liveFeed.src = `data:image/jpeg;base64,${image}`;
        }

        // Update Header/Meta
        deviceIdBadge.textContent = device_id || 'Unknown';
        conveyorStatus.textContent = conveyor_status === 'stopped' ? '⏹ Stopped' : '▶ Running';
        conveyorStatus.className = 'value ' + (conveyor_status === 'stopped' ? 'status-active' : '');
        
        metaFrameId.textContent = `#${frame_id}`;
        
        const now = Date.now();
        const latency = now - (timestamp * 1000);
        metaLatency.textContent = `${Math.round(latency)} ms`;
        
        const date = new Date(timestamp * 1000);
        metaTime.textContent = date.toLocaleTimeString();

        // Update Main Result
        const config = fruitConfig[safeLabel] || fruitConfig['unknown'];
        fruitIcon.textContent = config.icon;
        fruitIcon.style.borderColor = config.color;
        currentLabel.textContent = config.name;
        
        const confPercent = (confidence * 100).toFixed(1);
        confidenceBar.style.width = `${confPercent}%`;
        confidenceText.textContent = `${confPercent}%`;
        
        // Color confidence bar
        if (confidence > 0.8) confidenceBar.style.backgroundColor = 'var(--success)';
        else if (confidence > 0.5) confidenceBar.style.backgroundColor = 'var(--warning)';
        else confidenceBar.style.backgroundColor = 'var(--danger)';

        // Update Stats
        updateStats(safeLabel);

        // Update History
        addToHistory({
            frame_id,
            time: date.toLocaleTimeString(),
            label: config.name,
            icon: config.icon,
            confidence: confPercent,
            image: image
        });
    }

    function updateStats(label) {
        if (label === 'cam') stats.cam++;
        else if (label === 'chanh') stats.chanh++;
        else if (label === 'quyt') stats.quyt++;
        
        stats.total++;

        if (countCam) countCam.textContent = stats.cam;
        if (countChanh) countChanh.textContent = stats.chanh;
        if (countQuyt) countQuyt.textContent = stats.quyt;
        if (countTotal) countTotal.textContent = stats.total;
        
        // Animation effect
        const el = document.getElementById(`count-${label}`) || countTotal;
        if (el) {
            el.style.transform = 'scale(1.2)';
            setTimeout(() => el.style.transform = 'scale(1)', 200);
        }
    }

    function addToHistory(item) {
        history.unshift(item);
        if (history.length > MAX_HISTORY) history.pop();
        renderHistory();
    }

    function renderHistory() {
        if (!historyBody) return;
        historyBody.innerHTML = '';
        history.forEach((item, index) => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${item.frame_id}</td>
                <td>${item.time}</td>
                <td style="font-weight: 600">${item.icon} ${item.label}</td>
                <td>
                    <div class="confidence-mini-bar">
                        <div class="mini-bar-bg">
                            <div class="mini-bar-fill" style="width: ${item.confidence}%; background-color: ${getConfColor(item.confidence)}"></div>
                        </div>
                        <span>${item.confidence}%</span>
                    </div>
                </td>
                <td>
                    <div class="thumb-container" onclick="showPreview('${item.image}', '${item.label} - Frame #${item.frame_id}')">
                        <img src="data:image/jpeg;base64,${item.image}" class="history-thumb">
                    </div>
                </td>
            `;
            historyBody.appendChild(row);
        });
    }

    function getConfColor(val) {
        if (val > 80) return '#10b981';
        if (val > 50) return '#f59e0b';
        return '#ef4444';
    }

    // Modal / Preview
    window.showPreview = (imgBase64, title) => {
        if (!modal || !modalImg || !modalCaption) return;
        modal.style.display = "block";
        modalImg.src = `data:image/jpeg;base64,${imgBase64}`;
        modalCaption.textContent = title;
    };

    if (modalClose) {
        modalClose.onclick = () => modal.style.display = "none";
    }
    window.onclick = (event) => {
        if (event.target == modal) modal.style.display = "none";
    };

    // Actions
    if (btnClearHistory) {
        btnClearHistory.onclick = () => {
            if (confirm('Bạn có chắc chắn muốn xóa toàn bộ lịch sử?')) {
                history = [];
                stats = { cam: 0, chanh: 0, quyt: 0, total: 0 };
                if (countCam) countCam.textContent = '0';
                if (countChanh) countChanh.textContent = '0';
                if (countQuyt) countQuyt.textContent = '0';
                if (countTotal) countTotal.textContent = '0';
                renderHistory();
            }
        };
    }

    document.addEventListener('keydown', (event) => {
        // Check socket connection first for safety
        if (!socket || socket.readyState !== WebSocket.OPEN) return;
        
        // Then check event.target to avoid potential null reference
        const tagName = event.target && event.target.tagName ? event.target.tagName.toLowerCase() : '';
        if (tagName === 'input' || tagName === 'textarea' || event.target.isContentEditable) return;
        
        const label = manualKeyMap[event.key];
        if (!label || event.repeat) return;
        if (['ArrowLeft', 'ArrowDown', 'ArrowRight', 'ArrowUp'].includes(event.key)) {
            event.preventDefault();
        }

        const now = Date.now();
        if (now - lastCommandAt < COMMAND_DEBOUNCE_MS) return;
        lastCommandAt = now;

        socket.send(JSON.stringify({
            type: 'manual_command',
            command_id: `${now}-${Math.random().toString(36).slice(2, 10)}`,
            label,
            source_key: event.key
        }));
    });

    // Start
    connect();
});
