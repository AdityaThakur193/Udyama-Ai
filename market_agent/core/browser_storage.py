"""Browser-based persistence using IndexedDB for session data."""


def get_indexeddb_script() -> str:
    """Return JavaScript code for IndexedDB management."""
    return """
    <script>
    // Initialize IndexedDB for persistent storage across page refreshes
    window.UdyamaDBReady = false;
    let udyamaDB = null;
    
    function initIndexedDB() {
        return new Promise((resolve, reject) => {
            if (udyamaDB) {
                resolve(udyamaDB);
                return;
            }
            
            const request = indexedDB.open('UdyamaAI', 1);
            
            request.onerror = () => {
                console.error('IndexedDB error:', request.error);
                reject(request.error);
            };
            
            request.onsuccess = () => {
                udyamaDB = request.result;
                window.UdyamaDBReady = true;
                console.log('IndexedDB initialized successfully');
                resolve(udyamaDB);
            };
            
            request.onupgradeneeded = (event) => {
                const db = event.target.result;
                
                if (!db.objectStoreNames.contains('sessionData')) {
                    db.createObjectStore('sessionData', { keyPath: 'id' });
                    console.log('Created sessionData store');
                }
                
                if (!db.objectStoreNames.contains('chatHistory')) {
                    const store = db.createObjectStore('chatHistory', { keyPath: 'id', autoIncrement: true });
                    store.createIndex('timestamp', 'timestamp', { unique: false });
                    console.log('Created chatHistory store');
                }
            };
        });
    }
    
    function saveSessionData(key, data) {
        if (!udyamaDB) return Promise.resolve(null);
        
        return new Promise((resolve, reject) => {
            try {
                const transaction = udyamaDB.transaction(['sessionData'], 'readwrite');
                const store = transaction.objectStore('sessionData');
                const item = { 
                    id: key, 
                    data: JSON.stringify(data),
                    timestamp: Date.now() 
                };
                const request = store.put(item);
                
                request.onerror = () => reject(request.error);
                request.onsuccess = () => {
                    console.log('Saved to IndexedDB:', key);
                    resolve(request.result);
                };
            } catch (err) {
                console.error('Error saving to IndexedDB:', err);
                reject(err);
            }
        });
    }
    
    function getSessionData(key) {
        if (!udyamaDB) return Promise.resolve(null);
        
        return new Promise((resolve, reject) => {
            try {
                const transaction = udyamaDB.transaction(['sessionData'], 'readonly');
                const store = transaction.objectStore('sessionData');
                const request = store.get(key);
                
                request.onerror = () => reject(request.error);
                request.onsuccess = () => {
                    const result = request.result ? JSON.parse(request.result.data) : null;
                    console.log('Retrieved from IndexedDB:', key, result);
                    resolve(result);
                };
            } catch (err) {
                console.error('Error retrieving from IndexedDB:', err);
                reject(err);
            }
        });
    }
    
    function addChatMessage(message) {
        if (!udyamaDB) return Promise.resolve(null);
        
        return new Promise((resolve, reject) => {
            try {
                const transaction = udyamaDB.transaction(['chatHistory'], 'readwrite');
                const store = transaction.objectStore('chatHistory');
                const item = {
                    question: message.question,
                    answer: message.answer,
                    timestamp: Date.now()
                };
                const request = store.add(item);
                
                request.onerror = () => reject(request.error);
                request.onsuccess = () => {
                    console.log('Chat message saved');
                    resolve(request.result);
                };
            } catch (err) {
                console.error('Error saving chat message:', err);
                reject(err);
            }
        });
    }
    
    function getChatHistory() {
        if (!udyamaDB) return Promise.resolve([]);
        
        return new Promise((resolve, reject) => {
            try {
                const transaction = udyamaDB.transaction(['chatHistory'], 'readonly');
                const store = transaction.objectStore('chatHistory');
                const request = store.getAll();
                
                request.onerror = () => reject(request.error);
                request.onsuccess = () => {
                    const messages = request.result.map(item => ({
                        question: item.question,
                        answer: item.answer
                    }));
                    console.log('Retrieved chat history:', messages.length, 'messages');
                    resolve(messages);
                };
            } catch (err) {
                console.error('Error retrieving chat history:', err);
                reject(err);
            }
        });
    }
    
    function clearChatHistory() {
        if (!udyamaDB) return Promise.resolve();
        
        return new Promise((resolve, reject) => {
            try {
                const transaction = udyamaDB.transaction(['chatHistory'], 'readwrite');
                const store = transaction.objectStore('chatHistory');
                const request = store.clear();
                
                request.onerror = () => reject(request.error);
                request.onsuccess = () => {
                    console.log('Chat history cleared');
                    resolve();
                };
            } catch (err) {
                console.error('Error clearing chat history:', err);
                reject(err);
            }
        });
    }
    
    function deleteSessionData(key) {
        if (!udyamaDB) return Promise.resolve();
        
        return new Promise((resolve, reject) => {
            try {
                const transaction = udyamaDB.transaction(['sessionData'], 'readwrite');
                const store = transaction.objectStore('sessionData');
                const request = store.delete(key);
                
                request.onerror = () => reject(request.error);
                request.onsuccess = () => {
                    console.log('Deleted from IndexedDB:', key);
                    resolve();
                };
            } catch (err) {
                console.error('Error deleting from IndexedDB:', err);
                reject(err);
            }
        });
    }
    
    // Initialize DB on page load
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            initIndexedDB().catch(err => console.log('IndexedDB unavailable:', err));
        });
    } else {
        initIndexedDB().catch(err => console.log('IndexedDB unavailable:', err));
    }
    
    // Expose API
    window.UdyamaStorage = {
        init: initIndexedDB,
        saveSession: saveSessionData,
        getSession: getSessionData,
        addChatMsg: addChatMessage,
        getChatHist: getChatHistory,
        clearChatHist: clearChatHistory,
        deleteSession: deleteSessionData,
        isReady: () => window.UdyamaDBReady
    };
    
    console.log('UdyamaStorage API loaded');
    </script>
    """
