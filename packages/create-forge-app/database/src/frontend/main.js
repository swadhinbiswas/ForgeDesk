/**
 * Forge Plain Template - Main JavaScript
 * 
 * This file demonstrates how to use the Forge IPC bridge
 * to call Python functions from the frontend.
 */

import forge, { invoke, isForgeAvailable, on } from '@forgedesk/api';

// Wait for Forge runtime to be ready
document.addEventListener('DOMContentLoaded', () => {
    console.log('[App] DOM loaded, Forge ready:', isForgeAvailable());
    document.getElementById('greetButton')?.addEventListener('click', greet);
    document.getElementById('systemInfoButton')?.addEventListener('click', getSystemInfo);
    document.getElementById('addButton')?.addEventListener('click', addNumbers);
});

/**
 * Call the greet Python command.
 */
async function greet() {
    const nameInput = document.getElementById('nameInput');
    const resultEl = document.getElementById('greetingResult');
    
    try {
        resultEl.textContent = 'Calling Python...';
        
        const result = await invoke('greet', { 
            name: nameInput.value || 'Developer' 
        });
        
        resultEl.textContent = result;
        
        // Copy to clipboard
        await forge.clipboard.write(result);
        console.log('[App] Result copied to clipboard');
        
    } catch (error) {
        resultEl.textContent = 'Error: ' + error.message;
        console.error('[App] Greet failed:', error);
    }
}

/**
 * Call the get_system_info Python command.
 */
async function getSystemInfo() {
    const resultEl = document.getElementById('systemInfo');
    
    try {
        resultEl.textContent = 'Loading...';
        
        const info = await invoke('get_system_info');
        
        resultEl.textContent = JSON.stringify(info, null, 2);
        
    } catch (error) {
        resultEl.textContent = 'Error: ' + error.message;
        console.error('[App] Get system info failed:', error);
    }
}

/**
 * Call the add_numbers Python command.
 */
async function addNumbers() {
    const numA = parseInt(document.getElementById('numA').value) || 0;
    const numB = parseInt(document.getElementById('numB').value) || 0;
    const resultEl = document.getElementById('calcResult');
    
    try {
        resultEl.textContent = 'Calculating...';
        
        const result = await invoke('add_numbers', { 
            a: numA, 
            b: numB 
        });
        
        resultEl.textContent = `${numA} + ${numB} = ${result}`;
        
    } catch (error) {
        resultEl.textContent = 'Error: ' + error.message;
        console.error('[App] Add numbers failed:', error);
    }
}

/**
 * Example: Listen for events from Python
 */
on('progress_update', (data) => {
    console.log('[App] Progress update:', data);
});

/**
 * Example: Emit event to Python
 */
function emitExample() {
    forge.emit('user_action', { 
        action: 'button_click',
        timestamp: Date.now()
    });
}

window.emitExample = emitExample;
