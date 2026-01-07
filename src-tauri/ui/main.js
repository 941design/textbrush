// Test UI JavaScript for IPC verification

const { invoke } = window.__TAURI__.core;
const { listen } = window.__TAURI__.event;

let currentImage = null;

// Listen for sidecar messages
listen('sidecar-message', (event) => {
    const msg = event.payload;
    handleMessage(msg);
});

function handleMessage(msg) {
    const status = document.getElementById('status');
    const img = document.getElementById('image');
    const placeholder = document.querySelector('.placeholder');

    switch (msg.type) {
        case 'ready':
            status.textContent = 'Status: Model loaded, generating images...';
            break;

        case 'image_ready':
            currentImage = msg.payload;
            img.src = `data:image/png;base64,${msg.payload.image_data}`;
            img.style.display = 'block';
            placeholder.style.display = 'none';
            status.textContent =
                `Status: Image ready (seed: ${msg.payload.seed}, ` +
                `buffer: ${msg.payload.buffer_count}/${msg.payload.buffer_max})`;
            break;

        case 'buffer_status':
            status.textContent =
                `Status: Buffer ${msg.payload.count}/${msg.payload.max} ` +
                `(generating: ${msg.payload.generating ? 'yes' : 'no'})`;
            break;

        case 'accepted':
            status.textContent = `Status: Saved to ${msg.payload.path}`;
            setTimeout(() => window.close(), 1000);
            break;

        case 'aborted':
            status.textContent = 'Status: Aborted';
            setTimeout(() => window.close(), 500);
            break;

        case 'error':
            status.textContent = `Error: ${msg.payload.message}`;
            if (msg.payload.fatal) {
                setTimeout(() => window.close(), 2000);
            }
            break;

        default:
            console.log('Unknown message type:', msg.type);
    }
}

// Button handlers
document.getElementById('skip').onclick = () => {
    invoke('skip_image').catch(err => {
        console.error('Skip failed:', err);
        document.getElementById('status').textContent = `Error: ${err}`;
    });
};

document.getElementById('accept').onclick = () => {
    invoke('accept_image').catch(err => {
        console.error('Accept failed:', err);
        document.getElementById('status').textContent = `Error: ${err}`;
    });
};

document.getElementById('abort').onclick = () => {
    invoke('abort_generation').catch(err => {
        console.error('Abort failed:', err);
        document.getElementById('status').textContent = `Error: ${err}`;
    });
};

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    if (e.key === ' ' || e.key === 'ArrowRight') {
        e.preventDefault();
        invoke('skip_image');
    } else if (e.key === 'Enter') {
        e.preventDefault();
        invoke('accept_image');
    } else if (e.key === 'Escape') {
        e.preventDefault();
        invoke('abort_generation');
    }
});

// Start generation when window opens
// Test prompt for verification
invoke('init_generation', {
    prompt: 'A watercolor painting of a cat',
    outputPath: null,
    seed: null,
    aspectRatio: '1:1'
}).then(() => {
    console.log('Generation initialized');
}).catch(err => {
    console.error('Init failed:', err);
    document.getElementById('status').textContent = `Error: ${err}`;
});
