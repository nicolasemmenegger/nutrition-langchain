class NutritionChat {
    constructor() {
        this.foods = [];
        this.totalNutrition = { calories: 0, protein: 0, carbs: 0, fat: 0 };
        this.currentImage = null;
        this.apiUrl = 'http://localhost:8001';
        this.init();
    }

    async init() {
        this.loadData();
        this.setupEventListeners();
        this.updateNutritionDisplay();
        await this.checkBackendConnection();
    }

    setupEventListeners() {
        const chatInput = document.getElementById('chat-input');
        const sendBtn = document.getElementById('send-btn');
        const imageBtn = document.getElementById('image-btn');
        const imageUpload = document.getElementById('image-upload');
        const removeImageBtn = document.getElementById('remove-image');

        sendBtn.addEventListener('click', () => this.sendMessage());
        chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        imageBtn.addEventListener('click', () => imageUpload.click());
        imageUpload.addEventListener('change', (e) => this.handleImageUpload(e));
        removeImageBtn.addEventListener('click', () => this.removeImage());

        chatInput.addEventListener('input', () => {
            sendBtn.disabled = !chatInput.value.trim() && !this.currentImage;
        });
    }

    handleImageUpload(event) {
        const file = event.target.files[0];
        if (file && file.type.startsWith('image/')) {
            const reader = new FileReader();
            reader.onload = (e) => {
                this.currentImage = {
                    file: file,
                    dataUrl: e.target.result,
                    name: file.name
                };
                this.showImagePreview();
                document.getElementById('send-btn').disabled = false;
            };
            reader.readAsDataURL(file);
        }
    }

    showImagePreview() {
        const preview = document.getElementById('image-preview');
        const previewImg = document.getElementById('preview-img');
        previewImg.src = this.currentImage.dataUrl;
        preview.style.display = 'block';
    }

    removeImage() {
        this.currentImage = null;
        document.getElementById('image-preview').style.display = 'none';
        document.getElementById('image-upload').value = '';
        const chatInput = document.getElementById('chat-input');
        document.getElementById('send-btn').disabled = !chatInput.value.trim();
    }

    // Helper to build multipart/form-data for /chat-vision
    buildFormData(fields = {}, files = {}) {
        const fd = new FormData();
        Object.entries(fields).forEach(([k, v]) => {
            if (v !== undefined && v !== null) fd.append(k, String(v));
        });
        Object.entries(files).forEach(([k, file]) => {
            if (file) fd.append(k, file, file.name || 'upload');
        });
        return fd;
    }

    async sendMessage() {
        const chatInput = document.getElementById('chat-input');
        const message = chatInput.value.trim();
        const imageSnapshot = this.currentImage; // snapshot so we can render & send it

        if (!message && !imageSnapshot) return;

        this.addUserMessage(message, imageSnapshot);
        chatInput.value = '';
        this.removeImage();
        document.getElementById('send-btn').disabled = true;

        this.showTypingIndicator();
        try {
            await this.processMessage(message, imageSnapshot);
        } finally {
            this.hideTypingIndicator();
        }
    }

    addUserMessage(text, image = null) {
        const messagesContainer = document.getElementById('chat-messages');
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message user-message';

        let imageHtml = '';
        if (image) {
            imageHtml = `<img src="${image.dataUrl}" alt="User uploaded image" class="message-image">`;
        }

        messageDiv.innerHTML = `
            <div class="message-content">
                <div class="avatar">👤</div>
                <div class="text">
                    ${text || 'Uploaded an image'}
                    ${imageHtml}
                </div>
            </div>
        `;

        messagesContainer.appendChild(messageDiv);
        this.scrollToBottom();
    }

    addBotMessage(text) {
        const messagesContainer = document.getElementById('chat-messages');
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message bot-message';

        messageDiv.innerHTML = `
            <div class="message-content">
                <div class="avatar">🤖</div>
                <div class="text">${text}</div>
            </div>
        `;

        messagesContainer.appendChild(messageDiv);
        this.scrollToBottom();
    }

    showTypingIndicator() {
        const messagesContainer = document.getElementById('chat-messages');
        const typingDiv = document.createElement('div');
        typingDiv.className = 'message bot-message typing-indicator-msg';
        typingDiv.innerHTML = `
            <div class="message-content">
                <div class="avatar">🤖</div>
                <div class="typing-indicator">
                    Analyzing...
                    <div class="typing-dots">
                        <div class="typing-dot"></div>
                        <div class="typing-dot"></div>
                        <div class="typing-dot"></div>
                    </div>
                </div>
            </div>
        `;
        messagesContainer.appendChild(typingDiv);
        this.scrollToBottom();
    }

    hideTypingIndicator() {
        const typingIndicator = document.querySelector('.typing-indicator-msg');
        if (typingIndicator) {
            typingIndicator.remove();
        }
    }

    async processMessage(message, image = null) {
        if (image) {
            await this.chatWithVision(
                message || "Please analyze this meal image for nutrition insights.",
                image
            );
        } else {
            await this.chatWithAPI(message);
        }
    }

    async checkBackendConnection() {
        try {
            const response = await fetch(`${this.apiUrl}/health`);
            if (response.ok) {
                const data = await response.json();
                if (data.openai_initialized) {
                    this.showConnectionStatus('🚀 Connected to AI nutrition coach!', 'success');
                } else {
                    this.showConnectionStatus('❌ Backend connected but OpenAI not initialized. Please restart backend with valid API key.', 'error');
                    this.disableInterface();
                }
            } else {
                this.showConnectionStatus('❌ Backend server not available. Please start the backend first.', 'error');
                this.disableInterface();
            }
        } catch (error) {
            this.showConnectionStatus('❌ Cannot connect to backend server. Please start the backend first.', 'error');
            this.disableInterface();
        }
    }

    showConnectionStatus(message, type = 'info') {
        const statusDiv = document.createElement('div');
        statusDiv.className = `connection-status ${type}`;
        statusDiv.textContent = message;
        
        // Insert at the top of chat messages
        const messagesContainer = document.getElementById('chat-messages');
        const firstMessage = messagesContainer.firstChild;
        messagesContainer.insertBefore(statusDiv, firstMessage);
        
        // Don't auto-remove error messages
        if (type !== 'error') {
            setTimeout(() => statusDiv.remove(), 5000);
        }
    }

    disableInterface() {
        const chatInput = document.getElementById('chat-input');
        const sendBtn = document.getElementById('send-btn');
        const imageBtn = document.getElementById('image-btn');
        
        chatInput.disabled = true;
        chatInput.placeholder = 'Backend required - please start the server first';
        sendBtn.disabled = true;
        imageBtn.disabled = true;
    }

    async chatWithAPI(message) {
        try {
            const response = await fetch(`${this.apiUrl}/chat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ 
                    message: message,
                    session_id: "default"
                })
            });

            if (!response.ok) {
                throw new Error(`API request failed: ${response.status}`);
            }

            const data = await response.json();
            
            if (data.success) {
                this.addBotMessage(data.message);
            } else {
                throw new Error(data.message || 'Chat failed');
            }
        } catch (error) {
            console.error('Chat API failed:', error);
            this.addBotMessage(
                `❌ Chat failed: ${error.message}. Please check that the backend is running and try again.`
            );
        }
    }

    // NEW: send text + image to /chat-vision via multipart/form-data
    async chatWithVision(message, imageObj) {
        try {
            const form = this.buildFormData(
                {
                    message,
                    session_id: "default",
                    model: "gpt-4o-mini", // optional; align with backend default if you change it
                    temperature: 0.2
                },
                {
                    image: imageObj?.file
                }
            );

            const response = await fetch(`${this.apiUrl}/chat-vision`, {
                method: 'POST',
                body: form
            });

            if (!response.ok) throw new Error(`Vision request failed: ${response.status}`);

            const data = await response.json();
            if (data.success) {
                this.addBotMessage(data.message);
            } else {
                throw new Error(data.message || 'Vision chat failed');
            }
        } catch (error) {
            console.error('Vision API failed:', error);
            this.addBotMessage(`❌ Vision chat failed: ${error.message}.`);
        }
    }

    updateNutritionDisplay() {
        // Keep the display as is - user can manually update if needed
        // Or remove this if no longer tracking nutrition in the interface
    }

    showSuccessToast(message) {
        const toast = document.createElement('div');
        toast.className = 'success-toast';
        toast.textContent = message;
        document.body.appendChild(toast);
        
        setTimeout(() => toast.classList.add('show'), 100);
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    scrollToBottom() {
        const messagesContainer = document.getElementById('chat-messages');
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    saveData() {
        try {
            localStorage.setItem('nutritionChatData', JSON.stringify({
                totalNutrition: this.totalNutrition,
                lastSaved: new Date().toISOString()
            }));
        } catch (error) {
            console.error('Error saving data:', error);
        }
    }

    loadData() {
        try {
            const saved = localStorage.getItem('nutritionChatData');
            if (saved) {
                const data = JSON.parse(saved);
                this.totalNutrition = data.totalNutrition || { calories: 0, protein: 0, carbs: 0, fat: 0 };
            }
        } catch (error) {
            console.error('Error loading data:', error);
        }
    }
}

// Initialize the app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new NutritionChat();
});
