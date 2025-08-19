// Chat Interface JavaScript
class NutritionChat {
    constructor() {
        this.chatMessages = document.getElementById('chatMessages');
        this.messageInput = document.getElementById('messageInput');
        this.chatForm = document.getElementById('chatForm');
        this.imageInput = document.getElementById('imageInput');
        this.sidePanel = document.getElementById('sidePanel');
        
        this.currentImage = null;
        this.pendingMealData = null;
        this.pendingRecipeData = null;
        
        this.init();
    }
    
    init() {
        // Form submission
        this.chatForm.addEventListener('submit', (e) => {
            e.preventDefault();
            this.sendMessage();
        });
        
        // Image handling
        this.imageInput.addEventListener('change', (e) => {
            this.handleImageSelect(e);
        });
        
        // Microphone handling
        this.micButton = document.getElementById('micButton');
        if (this.micButton) {
            this.micButton.addEventListener('click', () => this.toggleRecording());
        }
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.isRecording = false;

        document.getElementById('removeImage').addEventListener('click', () => {
            this.clearImage();
        });
        
        // Panel controls
        document.getElementById('closePanel').addEventListener('click', () => {
            this.closePanel();
        });
        
        // Clear chat
        document.getElementById('clearChat').addEventListener('click', () => {
            this.clearChat();
        });
        
        // Auto-resize message input
        this.messageInput.addEventListener('input', () => {
            this.autoResize();
        });
        
        // Handle Enter key (send) vs Shift+Enter (new line)
        this.messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // Load existing chat history on page load
        this.loadHistory();
    }
    async toggleRecording() {
        try {
            if (!this.isRecording) {
                if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                    alert('Microphone not supported in this browser');
                    return;
                }
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                const mime = MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : 'audio/ogg';
                this.mediaRecorder = new MediaRecorder(stream, { mimeType: mime });
                this.audioChunks = [];
                this.mediaRecorder.ondataavailable = (e) => {
                    if (e.data && e.data.size > 0) this.audioChunks.push(e.data);
                };
                this.mediaRecorder.onstop = async () => {
                    const blob = new Blob(this.audioChunks, { type: mime });
                    await this.sendAudioForTranscription(blob);
                    stream.getTracks().forEach(t => t.stop());
                };
                this.mediaRecorder.start();
                this.isRecording = true;
                this.setMicActive(true);
            } else {
                this.mediaRecorder.stop();
                this.isRecording = false;
                this.setMicActive(false);
            }
        } catch (e) {
            console.error('Recording error', e);
            this.isRecording = false;
            this.setMicActive(false);
        }
    }

    setMicActive(active) {
        try {
            this.micButton.classList.toggle('active', !!active);
            this.micButton.innerHTML = active ? '<i class="fas fa-stop"></i>' : '<i class="fas fa-microphone"></i>';
        } catch {}
    }

    async sendAudioForTranscription(blob) {
        try {
            const fd = new FormData();
            fd.append('audio', blob, 'voice.webm');
            const resp = await fetch('/api/transcribe_audio', { method: 'POST', body: fd });
            const data = await resp.json();
            if (data && data.text) {
                // Place the transcribed text into the message input and send
                this.messageInput.value = data.text;
                this.sendMessage();
            } else {
                console.warn('No transcription text returned', data);
            }
        } catch (e) {
            console.error('Transcription error', e);
        }
    }
    
    async sendMessage() {
        const message = this.messageInput.value.trim();
        
        if (!message && !this.currentImage) {
            return;
        }
        
        // Store image reference before clearing
        const imageToSend = this.currentImage;
        
        // Add user message to chat
        this.addMessage(message, 'user', this.currentImage);
        
        // Clear input
        this.messageInput.value = '';
        this.clearImage();
        
        // Show loading
        this.showLoading();
        
        // Prepare form data
        const formData = new FormData();
        formData.append('message', message);
        
        if (imageToSend) {
            formData.append('image', imageToSend);
            console.log('Sending image with message:', message);
        }
        
        try {
            const response = await fetch('/api/ai_chat', {
                method: 'POST',
                body: formData,
                credentials: 'same-origin'
            });
            
            const data = await response.json();
            
            // Hide loading
            this.hideLoading();
            
            // Debug log to see what's returned
            console.log('Response data:', data);
            
            // Add assistant response only if it's not empty
            // (analyzer and recipe generator return empty strings since their output goes to side panel)
            if (data.reply_html && data.reply_html.trim() !== '') {
                this.addMessage(data.reply_html, 'assistant', null, true);
            }
            
            // Handle side panel data if present
            if (data.side_panel_data) {
                console.log('Side panel data received:', data.side_panel_data);
                if (data.side_panel_data.type === 'meal') {
                    console.log('Opening meal panel with items:', data.side_panel_data.items);
                    this.showMealPanel(data.side_panel_data);
                } else if (data.side_panel_data.type === 'recipe') {
                    console.log('Opening recipe panel');
                    this.showRecipePanel(data.side_panel_data.recipe);
                }
            }
            
            // Fallback to old logic for backward compatibility
            else if (data.category === 'analyze_meal' && data.items && data.items.length > 0) {
                console.log('Opening meal panel with items (legacy):', data.items);
                this.showMealPanel(data);
            } else if (data.category === 'recipe_generation' && data.recipe) {
                console.log('Opening recipe panel (legacy)');
                this.showRecipePanel(data.recipe);
            } else if (data.category === 'web_search' && data.nutrition_data) {
                // For web search results, we might want to show a simplified meal panel
                if (data.nutrition_data.found) {
                    console.log('Showing nutrition info');
                    this.showNutritionInfo(data.nutrition_data);
                }
            } else {
                console.log('No panel action taken. Category:', data.category, 'Items:', data.items);
            }
            
            // Scroll to bottom
            this.scrollToBottom();
            
        } catch (error) {
            console.error('Error:', error);
            this.hideLoading();
            this.addMessage('Sorry, there was an error processing your request. Please try again.', 'assistant');
        }
    }

    async loadHistory() {
        try {
            const res = await fetch('/api/chat_history', { credentials: 'same-origin' });
            const data = await res.json();
            if (Array.isArray(data.messages)) {
                // Only display messages from users or the conversation agent
                data.messages.forEach((m) => {
                    // Show user messages and assistant messages from the conversation agent only
                    if (m.role === 'user' || (m.role === 'assistant' && m.name === 'conversation')) {
                        this.addMessage(m.content, m.role, null, true);
                    }
                });
                this.scrollToBottom();
            }
        } catch (e) {
            console.error('Failed to load history', e);
        }
    }
    
    addMessage(content, sender, image = null, isHtml = false) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}-message`;
        
        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        avatar.innerHTML = sender === 'user' ? '<i class="fas fa-user"></i>' : '<i class="fas fa-robot"></i>';
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        
        if (image && sender === 'user') {
            const imgElement = document.createElement('img');
            imgElement.src = URL.createObjectURL(image);
            imgElement.className = 'message-image';
            contentDiv.appendChild(imgElement);
        }
        
        if (content) {
            if (isHtml) {
                contentDiv.innerHTML += content;
            } else {
                const p = document.createElement('p');
                p.textContent = content;
                contentDiv.appendChild(p);
            }
        }
        
        messageDiv.appendChild(avatar);
        messageDiv.appendChild(contentDiv);
        
        this.chatMessages.appendChild(messageDiv);
        this.scrollToBottom();
    }
    
    showMealPanel(data) {
        // Clone the meal log template
        const template = document.getElementById('mealLogTemplate');
        const content = template.content.cloneNode(true);
        
        // Clear and set panel content
        const panelContent = document.getElementById('panelContent');
        panelContent.innerHTML = '';
        panelContent.appendChild(content);
        
        // Populate ingredients
        const ingredientsList = document.getElementById('ingredientsList');
        data.items.forEach((item, index) => {
            const ingredientDiv = document.createElement('div');
            ingredientDiv.className = 'ingredient-item';
            // Keep original mapping to preserve ids when name unchanged
            if (item.ingredient_id != null) ingredientDiv.dataset.ingredientId = String(item.ingredient_id);
            if (item.ingredient_name != null) ingredientDiv.dataset.originalName = String(item.ingredient_name);
            ingredientDiv.innerHTML = `
                <div class="ingredient-info">
                    <input type="text" 
                           value="${item.ingredient_name ?? ''}" 
                           class="ingredient-name-input">
                    <input type="number" 
                           value="${item.grams ?? ''}" 
                           class="ingredient-amount-input"
                           min="0"
                           step="0.1">
                    <span class="unit">g</span>
                </div>
                <button type="button" class="btn-remove-ingredient">
                    <i class="fas fa-times"></i>
                </button>
            `;
            ingredientsList.appendChild(ingredientDiv);
        });
        
        // Store meal data for later
        this.pendingMealData = data;
        
        // Set panel actions
        const panelActions = document.getElementById('panelActions');
        panelActions.innerHTML = `
            <button class="btn-primary" onclick="nutritionChat.confirmMeal()">
                <i class="fas fa-check"></i> Log Meal
            </button>
        `;
        
        // Update panel title
        document.getElementById('panelTitle').textContent = 'Review Your Meal';
        
        // Wire up interactions
        ingredientsList.addEventListener('click', (e) => {
            const btn = e.target.closest('.btn-remove-ingredient');
            if (!btn) return;
            const row = btn.closest('.ingredient-item');
            if (row) row.remove();
            this.computeAndRenderNutrition();
        });

        ingredientsList.addEventListener('input', (e) => {
            if (e.target.matches('.ingredient-name-input') || e.target.matches('.ingredient-amount-input')) {
                this.debouncedCompute();
            }
        });

        // Meal type scroller chips
        const scroller = document.getElementById('mealTypeScroller');
        if (scroller) {
            const defaultType = this._defaultMealTypeForNow();
            let active = null;
            const chips = scroller.querySelectorAll('.meal-type-chip');
            chips.forEach(btn => {
                if (btn.dataset.type === defaultType && !active) {
                    active = btn;
                }
                btn.addEventListener('click', () => {
                    this._setMealTypeChipActive(btn);
                    this.selectedMealType = btn.dataset.type;
                });
            });
            if (!active && chips.length) active = chips[0];
            if (active) this._setMealTypeChipActive(active);
            this.selectedMealType = active ? active.dataset.type : defaultType;
        }

        // Default meal date to today
        const mealDate = document.getElementById('mealDate');
        if (mealDate) {
            try {
                const d = new Date();
                const yyyy = d.getFullYear();
                const mm = String(d.getMonth() + 1).padStart(2, '0');
                const dd = String(d.getDate()).padStart(2, '0');
                mealDate.value = `${yyyy}-${mm}-${dd}`;
            } catch {}
        }

        // Show panel
        this.openPanel();
        // Initial compute
        this.computeAndRenderNutrition();
    }
    
    showRecipePanel(recipe) {
        // Clone the recipe template
        const template = document.getElementById('recipeTemplate');
        const content = template.content.cloneNode(true);
        
        // Clear and set panel content
        const panelContent = document.getElementById('panelContent');
        panelContent.innerHTML = '';
        panelContent.appendChild(content);
        
        // Populate recipe details
        document.getElementById('recipeName').textContent = recipe.recipe_name;
        document.getElementById('recipeDescription').textContent = recipe.description;
        document.getElementById('recipeTime').textContent = `${recipe.prep_time} min prep, ${recipe.cook_time} min cook`;
        document.getElementById('recipeServings').textContent = `${recipe.servings} servings`;
        
        // Ingredients
        const ingredientsList = document.getElementById('recipeIngredients');
        recipe.ingredients.forEach(ing => {
            const li = document.createElement('li');
            li.innerHTML = `
                <span class="ingredient-amount">${ing.amount}</span> 
                <span class="ingredient-name">${ing.name}</span>
            `;
            ingredientsList.appendChild(li);
        });
        
        // Instructions
        const instructionsList = document.getElementById('recipeInstructions');
        recipe.instructions.forEach(step => {
            const li = document.createElement('li');
            li.textContent = step;
            instructionsList.appendChild(li);
        });
        
        // Nutrition
        const nutritionGrid = document.getElementById('recipeNutrition');
        const nutrition = recipe.nutrition_per_serving;
        nutritionGrid.innerHTML = `
            <div class="nutrition-item">
                <span class="label">Calories:</span>
                <span class="value">${nutrition.calories}</span>
            </div>
            <div class="nutrition-item">
                <span class="label">Protein:</span>
                <span class="value">${nutrition.protein}g</span>
            </div>
            <div class="nutrition-item">
                <span class="label">Carbs:</span>
                <span class="value">${nutrition.carbs}g</span>
            </div>
            <div class="nutrition-item">
                <span class="label">Fat:</span>
                <span class="value">${nutrition.fat}g</span>
            </div>
        `;
        
        // Store recipe data
        this.pendingRecipeData = recipe;
        
        // Set panel actions
        const panelActions = document.getElementById('panelActions');
        panelActions.innerHTML = `
            <button class="btn-primary" onclick="nutritionChat.logRecipeAsMeal()">
                <i class="fas fa-utensils"></i> Log as Meal
            </button>
            <button class="btn-secondary" onclick="nutritionChat.saveRecipe()">
                <i class="fas fa-bookmark"></i> Save Recipe
            </button>
        `;
        
        // Update panel title
        document.getElementById('panelTitle').textContent = 'Recipe Suggestion';
        
        // Show panel
        this.openPanel();
    }
    
    showNutritionInfo(nutritionData) {
        // Create a simplified meal entry from web search results
        const mealData = {
            items: [{
                ingredient_name: nutritionData.food_name,
                grams: 100,
                nutrition: nutritionData.per_100g
            }]
        };
        
        this.showMealPanel(mealData);
        
        // Add confidence note
        const panelContent = document.getElementById('panelContent');
        const confidenceNote = document.createElement('div');
        confidenceNote.className = 'confidence-note';
        confidenceNote.innerHTML = `
            <p><small>Data confidence: ${nutritionData.confidence}</small></p>
            <p><small>Source: Web search results</small></p>
        `;
        panelContent.appendChild(confidenceNote);
    }
    
    confirmMeal() {
        // Collect updated meal data from DOM
        const updatedItems = this.collectItemsFromPanel();
        const notes = document.getElementById('mealNotes').value;
        const mealDate = (document.getElementById('mealDate')?.value || '').trim();
        this.logMeal(updatedItems, notes, this.selectedMealType, mealDate);
        this.closePanel();
    }
    
    async logMeal(items, notes, mealType, dateStr) {
        // Send to backend to save meal
        try {
            const response = await fetch('/api/log_meal', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    items: items,
                    notes: notes,
                    meal_type: mealType,
                    date: dateStr,
                    timestamp: new Date().toISOString()
                })
            });
            
            const data = await response.json();
            console.log('Meal logged:', data);
        } catch (error) {
            console.error('Error logging meal:', error);
        }
    }
    
    logRecipeAsMeal() {
        if (!this.pendingRecipeData) return;
        
        // Convert recipe ingredients to meal items
        const items = this.pendingRecipeData.ingredients.map(ing => ({
            ingredient_name: ing.name,
            grams: ing.grams || 100  // Default to 100g if not specified
        }));
        
        this.logMeal(items, `Recipe: ${this.pendingRecipeData.recipe_name}`, this.selectedMealType || this._defaultMealTypeForNow());
        
        this.closePanel();
        // Don't add a hardcoded message - let the backend handle appropriate responses
    }
    
    saveRecipe() {
        // Save recipe for later (would implement backend endpoint)
        console.log('Saving recipe:', this.pendingRecipeData);
        // Don't add a hardcoded message - let the backend handle appropriate responses
    }
    
    removeIngredient(index) {
        // Backward-compat: still support older inline onclick handlers
        const ingredientItem = document.querySelectorAll('.ingredient-item')[index];
        if (ingredientItem) {
            ingredientItem.remove();
            this.computeAndRenderNutrition();
        }
    }

    collectItemsFromPanel() {
        const rows = document.querySelectorAll('.ingredient-item');
        const items = [];
        rows.forEach(row => {
            const name = row.querySelector('.ingredient-name-input')?.value?.trim() || '';
            const grams = parseFloat(row.querySelector('.ingredient-amount-input')?.value || '0') || 0;
            if (!name || grams <= 0) return;
            const original = row.dataset.originalName || '';
            const ingId = row.dataset.ingredientId;
            const payload = { ingredient_name: name, grams: grams };
            if (ingId && original && original.toLowerCase() === name.toLowerCase()) {
                payload.ingredient_id = parseInt(ingId, 10);
            }
            items.push(payload);
        });
        return items;
    }

    updateNutritionSummaryUI(n) {
        try {
            document.getElementById('totalCalories').textContent = n.calories != null ? n.calories : 0;
            document.getElementById('totalProtein').textContent = (n.protein != null ? n.protein : 0) + 'g';
            document.getElementById('totalCarbs').textContent = (n.carbs != null ? n.carbs : 0) + 'g';
            document.getElementById('totalFat').textContent = (n.fat != null ? n.fat : 0) + 'g';
        } catch (e) {
            // No-op if elements not present
        }
    }

    async computeAndRenderNutrition() {
        const items = this.collectItemsFromPanel();
        if (!items.length) { this.updateNutritionSummaryUI({ calories: 0, protein: 0, carbs: 0, fat: 0 }); return; }
        try {
            const resp = await fetch('/api/compute_nutrition', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ items })
            });
            const data = await resp.json();
            const n = {
                calories: Math.round((data.calories || 0) * 10) / 10,
                protein: Math.round((data.protein || 0) * 10) / 10,
                carbs: Math.round((data.carbs || 0) * 10) / 10,
                fat: Math.round((data.fat || 0) * 10) / 10,
            };
            this.updateNutritionSummaryUI(n);
        } catch (e) {
            console.error('Failed to compute nutrition', e);
        }
    }

    debouncedCompute = (() => {
        let t = null;
        return () => {
            clearTimeout(t);
            t = setTimeout(() => this.computeAndRenderNutrition(), 250);
        };
    })();

    _defaultMealTypeForNow() {
        try {
            const now = new Date();
            const h = now.getHours();
            if (h < 11) return 'breakfast';
            if (h < 15) return 'lunch';
            if (h < 21) return 'dinner';
            return 'snack';
        } catch {
            return 'lunch';
        }
    }

    _setMealTypeChipActive(activeBtn) {
        try {
            const scroller = document.getElementById('mealTypeScroller');
            if (!scroller) return;
            scroller.querySelectorAll('.meal-type-chip').forEach(b => {
                b.style.backgroundColor = '#ffffff';
                b.style.color = '#1f2937'; // gray-800
                b.style.borderColor = '#d1d5db'; // gray-300
            });
            if (activeBtn) {
                activeBtn.style.backgroundColor = '#16a34a'; // green-600
                activeBtn.style.color = '#ffffff';
                activeBtn.style.borderColor = '#16a34a';
            }
        } catch {}
    }
    
    openPanel() {
        this.sidePanel.classList.add('panel-open');
    }
    
    closePanel() {
        this.sidePanel.classList.remove('panel-open');
        this.pendingMealData = null;
        this.pendingRecipeData = null;
    }
    
    handleImageSelect(e) {
        const file = e.target.files[0];
        if (file && file.type.startsWith('image/')) {
            this.currentImage = file;
            
            // Show preview
            const reader = new FileReader();
            reader.onload = (e) => {
                document.getElementById('previewImg').src = e.target.result;
                document.getElementById('imagePreview').style.display = 'block';
            };
            reader.readAsDataURL(file);
        }
    }
    
    clearImage() {
        this.currentImage = null;
        this.imageInput.value = '';
        document.getElementById('imagePreview').style.display = 'none';
    }
    
    clearChat() {
        if (confirm('Are you sure you want to clear the chat history?')) {
            fetch('/api/chat_history', { method: 'DELETE', credentials: 'same-origin' })
                .then(() => {
                    // Keep only the welcome message
                    const messages = this.chatMessages.querySelectorAll('.message');
                    for (let i = 1; i < messages.length; i++) {
                        messages[i].remove();
                    }
                })
                .catch((e) => console.error('Failed to clear chat', e));
        }
    }
    
    showLoading() {
        const loadingHTML = `
            <div class="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
            </div>
        `;
        this.addMessage(loadingHTML, 'assistant', null, true);
    }
    
    hideLoading() {
        const messages = this.chatMessages.querySelectorAll('.message');
        messages[messages.length - 1].remove();
    }
    
    scrollToBottom() {
        this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
    }
    
    autoResize() {
        // Reset height to auto to get correct scrollHeight
        this.messageInput.style.height = 'auto';
        // Set new height based on content, max 120px
        const newHeight = Math.min(this.messageInput.scrollHeight, 120);
        this.messageInput.style.height = newHeight + 'px';
    }
}

// Initialize the chat when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.nutritionChat = new NutritionChat();
});