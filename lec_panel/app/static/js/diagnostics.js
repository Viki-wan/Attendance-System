/**
 * FIXED Diagnostic Script for Attendance System
 * Helps identify initialization issues
 */

(function() {
    'use strict';
    
    console.log('🔍 Diagnostics script loading...');
    
    // Wait for DOM to be fully loaded
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initDiagnostics);
    } else {
        // DOM already loaded, wait a bit for other scripts
        setTimeout(initDiagnostics, 1000);
    }
    
    function initDiagnostics() {
        console.log('\n========== INITIAL DIAGNOSTICS ==========');
        checkDOMElements();
        checkLibraries();
        checkClasses();
        
        // Check instances after a delay (they're created asynchronously)
        setTimeout(() => {
            checkInstances();
            console.log('========================================\n');
        }, 3000);
        
        // Add diagnostic UI
        setTimeout(addDiagnosticUI, 2000);
    }
    
    function checkDOMElements() {
        console.log('📋 Checking DOM Elements:');
        
        const requiredElements = [
            'session-id',
            'user-id', 
            'class-id',
            'camera-canvas',
            'start-camera-btn',
            'stop-camera-btn',
            'recognition-status',
            'present-count',
            'late-count',
            'absent-count',
            'student-list',
            'recent-recognitions-feed',
            'attendance-timeline',
            'toast-container'
        ];
        
        let foundCount = 0;
        requiredElements.forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                console.log(`  ✅ ${id}`);
                foundCount++;
            } else {
                console.error(`  ❌ ${id}: NOT FOUND`);
            }
        });
        
        console.log(`  Found ${foundCount}/${requiredElements.length} required elements\n`);
    }
    
    function checkLibraries() {
        console.log('📚 Checking External Libraries:');
        
        const libraries = {
            'Socket.IO': typeof io !== 'undefined',
            'Bootstrap': typeof bootstrap !== 'undefined',
            'jQuery': typeof $ !== 'undefined'
        };
        
        Object.entries(libraries).forEach(([name, loaded]) => {
            if (loaded) {
                console.log(`  ✅ ${name}`);
            } else {
                console.warn(`  ⚠️  ${name}: Not loaded`);
            }
        });
        console.log('');
    }
    
    function checkClasses() {
        console.log('🏗️  Checking Classes:');
        
        const classes = {
            'CameraHandler': window.CameraHandler,
            'AttendanceRealtimeHandler': window.AttendanceRealtimeHandler,
            'ProgressTracker': window.ProgressTracker
        };
        
        Object.entries(classes).forEach(([name, cls]) => {
            if (cls && typeof cls === 'function') {
                console.log(`  ✅ ${name}`);
            } else {
                console.error(`  ❌ ${name}: NOT DEFINED`);
            }
        });
        console.log('');
    }
    
    function checkInstances() {
        console.log('🎯 Checking Instances:');
        
        const instances = {
            'cameraHandler': window.cameraHandler,
            'attendanceHandler': window.attendanceHandler,
            'progressTracker': window.progressTracker
        };
        
        Object.entries(instances).forEach(([name, instance]) => {
            if (instance) {
                console.log(`  ✅ ${name}: Created`);
                console.log(`     Type: ${instance.constructor.name}`);
                
                // Additional checks
                if (name === 'cameraHandler') {
                    console.log(`     Active: ${instance.isActive || false}`);
                    console.log(`     Canvas: ${instance.canvas ? 'Found' : 'Not found'}`);
                }
                if (name === 'attendanceHandler') {
                    console.log(`     Socket connected: ${instance.socket?.connected || false}`);
                }
            } else {
                console.error(`  ❌ ${name}: NOT CREATED`);
            }
        });
        console.log('');
    }
    
    function addDiagnosticUI() {
        // Only add if we're on the live attendance page
        const canvas = document.getElementById('camera-canvas');
        if (!canvas) return;
        
        // Create floating diagnostic button
        const toggleBtn = document.createElement('button');
        toggleBtn.id = 'diag-toggle-btn';
        toggleBtn.innerHTML = '🔧';
        toggleBtn.style.cssText = `
            position: fixed;
            bottom: 20px;
            left: 20px;
            width: 50px;
            height: 50px;
            background: rgba(0, 0, 0, 0.8);
            color: white;
            border: 2px solid #007bff;
            border-radius: 50%;
            cursor: pointer;
            z-index: 9998;
            font-size: 24px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            transition: all 0.3s ease;
        `;
        toggleBtn.onmouseover = () => {
            toggleBtn.style.transform = 'scale(1.1)';
            toggleBtn.style.background = 'rgba(0, 123, 255, 0.9)';
        };
        toggleBtn.onmouseout = () => {
            toggleBtn.style.transform = 'scale(1)';
            toggleBtn.style.background = 'rgba(0, 0, 0, 0.8)';
        };
        toggleBtn.onclick = toggleDiagnosticPanel;
        document.body.appendChild(toggleBtn);
        
        // Create diagnostic panel
        const panel = document.createElement('div');
        panel.id = 'diagnostic-panel';
        panel.style.cssText = `
            position: fixed;
            bottom: 80px;
            left: 20px;
            background: rgba(0, 0, 0, 0.95);
            color: white;
            padding: 20px;
            border-radius: 12px;
            z-index: 9999;
            font-family: 'Courier New', monospace;
            font-size: 13px;
            max-width: 400px;
            max-height: 70vh;
            overflow-y: auto;
            display: none;
            box-shadow: 0 8px 32px rgba(0,0,0,0.5);
            border: 2px solid #007bff;
        `;
        
        panel.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; border-bottom: 2px solid #007bff; padding-bottom: 10px;">
                <strong style="font-size: 16px;">🔧 System Diagnostics</strong>
                <button id="close-diagnostic" style="background: transparent; border: none; color: white; cursor: pointer; font-size: 20px;">✕</button>
            </div>
            <div id="diagnostic-content" style="margin-bottom: 15px;"></div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
                <button id="test-camera-init" class="diag-btn">🎥 Test Camera</button>
                <button id="test-socket" class="diag-btn">🔌 Test Socket</button>
                <button id="refresh-stats" class="diag-btn">📊 Refresh Stats</button>
                <button id="run-full-check" class="diag-btn">🔍 Full Check</button>
            </div>
        `;
        
        document.body.appendChild(panel);
        
        // Add styles
        const style = document.createElement('style');
        style.textContent = `
            .diag-btn {
                background: linear-gradient(135deg, #007bff 0%, #0056b3 100%);
                color: white;
                border: none;
                padding: 8px 12px;
                border-radius: 6px;
                cursor: pointer;
                font-size: 12px;
                font-weight: 600;
                transition: all 0.2s ease;
            }
            .diag-btn:hover {
                background: linear-gradient(135deg, #0056b3 0%, #004085 100%);
                transform: translateY(-2px);
                box-shadow: 0 4px 8px rgba(0,0,0,0.3);
            }
            .diag-btn:active {
                transform: translateY(0);
            }
            #diagnostic-panel::-webkit-scrollbar {
                width: 8px;
            }
            #diagnostic-panel::-webkit-scrollbar-track {
                background: rgba(255,255,255,0.1);
                border-radius: 4px;
            }
            #diagnostic-panel::-webkit-scrollbar-thumb {
                background: #007bff;
                border-radius: 4px;
            }
        `;
        document.head.appendChild(style);
        
        // Event listeners
        document.getElementById('close-diagnostic').onclick = () => {
            panel.style.display = 'none';
        };
        document.getElementById('test-camera-init').onclick = testCameraInit;
        document.getElementById('test-socket').onclick = testSocket;
        document.getElementById('refresh-stats').onclick = refreshStats;
        document.getElementById('run-full-check').onclick = runFullCheck;
        
        console.log('✅ Diagnostic UI added');
    }
    
    function toggleDiagnosticPanel() {
        const panel = document.getElementById('diagnostic-panel');
        if (panel.style.display === 'none') {
            panel.style.display = 'block';
            updateDiagnosticContent();
        } else {
            panel.style.display = 'none';
        }
    }
    
    window.updateDiagnosticContent = function() {
        const content = document.getElementById('diagnostic-content');
        if (!content) return;
        
        const canvas = document.getElementById('camera-canvas');
        const socket = window.attendanceHandler?.socket;
        
        const status = {
            canvas: !!canvas,
            cameraHandler: !!window.cameraHandler,
            attendanceHandler: !!window.attendanceHandler,
            progressTracker: !!window.progressTracker,
            socketConnected: socket?.connected || false,
            cameraActive: window.cameraHandler?.isActive || false
        };
        
        content.innerHTML = `
            <div style="line-height: 1.8;">
                <div style="margin-bottom: 10px; padding-bottom: 10px; border-bottom: 1px solid rgba(255,255,255,0.2);">
                    <strong style="color: #17a2b8;">System Status</strong>
                </div>
                <div style="display: grid; grid-template-columns: auto 1fr; gap: 8px; align-items: center;">
                    <span>Canvas:</span>
                    <span>${status.canvas ? '✅ Found' : '❌ Missing'}</span>
                    
                    <span>CameraHandler:</span>
                    <span>${status.cameraHandler ? '✅ Created' : '❌ Not Created'}</span>
                    
                    <span>AttendanceHandler:</span>
                    <span>${status.attendanceHandler ? '✅ Created' : '❌ Not Created'}</span>
                    
                    <span>ProgressTracker:</span>
                    <span>${status.progressTracker ? '✅ Created' : '❌ Not Created'}</span>
                    
                    <span>Socket:</span>
                    <span>${status.socketConnected ? '✅ Connected' : '⚠️ Disconnected'}</span>
                    
                    <span>Camera:</span>
                    <span>${status.cameraActive ? '🟢 Active' : '🔴 Inactive'}</span>
                </div>
            </div>
        `;
    };
    
    async function testCameraInit() {
        console.log('\n🎥 Testing Camera Initialization...');
        
        try {
            // Check if class exists
            if (typeof CameraHandler === 'undefined') {
                throw new Error('CameraHandler class not loaded');
            }
            console.log('✅ CameraHandler class found');
            
            // Check canvas
            const canvas = document.getElementById('camera-canvas');
            if (!canvas) {
                throw new Error('Canvas element not found');
            }
            console.log('✅ Canvas element found');
            
            // Check if instance exists
            if (!window.cameraHandler) {
                console.warn('⚠️  CameraHandler instance not created yet');
                alert('⚠️  Camera instance not created.\n\nThis is normal if the page just loaded.\nWait a few seconds and try again.');
                return;
            }
            console.log('✅ CameraHandler instance exists');
            
            // Check instance properties
            console.log('   Canvas:', window.cameraHandler.canvas?.id);
            console.log('   Active:', window.cameraHandler.isActive);
            console.log('   Context:', !!window.cameraHandler.ctx);
            
            alert('✅ Camera initialization test PASSED!\n\nCameraHandler is properly set up and ready to use.');
            
        } catch (error) {
            console.error('❌ Camera test failed:', error);
            alert('❌ Camera test FAILED:\n\n' + error.message);
        }
    }
    
    function testSocket() {
        console.log('\n🔌 Testing Socket Connection...');
        
        try {
            if (!window.attendanceHandler) {
                throw new Error('AttendanceHandler not initialized');
            }
            
            const socket = window.attendanceHandler.socket;
            
            if (!socket) {
                throw new Error('Socket object not found');
            }
            
            console.log('Socket ID:', socket.id);
            console.log('Connected:', socket.connected);
            console.log('Transport:', socket.io?.engine?.transport?.name);
            
            if (socket.connected) {
                alert('✅ Socket is CONNECTED!\n\nID: ' + socket.id);
            } else {
                alert('⚠️  Socket is NOT connected.\n\nIt may be attempting to reconnect...');
            }
            
        } catch (error) {
            console.error('❌ Socket test failed:', error);
            alert('❌ Socket test FAILED:\n\n' + error.message);
        }
    }
    
    async function refreshStats() {
        console.log('\n📊 Refreshing Statistics...');
        
        try {
            if (!window.progressTracker) {
                throw new Error('ProgressTracker not initialized');
            }
            
            await window.progressTracker.refresh();
            alert('✅ Statistics refreshed successfully!');
            
        } catch (error) {
            console.error('❌ Refresh failed:', error);
            alert('❌ Failed to refresh:\n\n' + error.message);
        }
    }
    
    function runFullCheck() {
        console.log('\n🔍 Running Full System Check...');
        console.log('========================================');
        
        checkDOMElements();
        checkLibraries();
        checkClasses();
        checkInstances();
        
        console.log('========================================');
        
        // Call the main checkInitialization if it exists
        if (typeof window.checkInitialization === 'function') {
            const result = window.checkInitialization();
            console.log('Initialization check result:', result);
        }
        
        updateDiagnosticContent();
        alert('✅ Full check complete!\n\nCheck browser console for detailed results.');
    }
    
    // Expose functions globally
    window.runDiagnostics = initDiagnostics;
    window.testCameraInit = testCameraInit;
    window.testSocket = testSocket;
    window.refreshStats = refreshStats;
    window.runFullCheck = runFullCheck;
    
    console.log('✅ Diagnostics script loaded');
    console.log('💡 Available commands:');
    console.log('   - runDiagnostics()');
    console.log('   - testCameraInit()');
    console.log('   - testSocket()');
    console.log('   - refreshStats()');
    console.log('   - runFullCheck()');
    console.log('   - checkInitialization() (from main script)');
    
})();