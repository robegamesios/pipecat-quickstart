/**
 * WebRTC Client for Pipecat Integration
 * 
 * This module provides WebRTC connectivity to the Pipecat server
 * for real-time voice communication with the avatar.
 */

export class PipecatWebRTCClient {
    constructor(options = {}) {
        this.serverUrl = options.serverUrl || 'ws://localhost:7860';
        this.onAudioReceived = options.onAudioReceived || null;
        this.onConnectionStateChange = options.onConnectionStateChange || null;
        this.onError = options.onError || null;
        
        this.websocket = null;
        this.peerConnection = null;
        this.localStream = null;
        this.remoteStream = null;
        this.isConnected = false;
        
        // WebRTC configuration
        this.rtcConfig = {
            iceServers: [
                { urls: 'stun:stun.l.google.com:19302' }
            ]
        };
        
        this.init();
    }
    
    async init() {
        console.log('🎙️ Initializing Pipecat WebRTC Client');
        
        try {
            // Get user media (microphone)
            this.localStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true,
                    sampleRate: 24000
                },
                video: false
            });
            
            console.log('🎤 Microphone access granted');
            
        } catch (error) {
            console.error('❌ Failed to get microphone access:', error);
            this.handleError(`Microphone access denied: ${error.message}`);
        }
    }
    
    async connect() {
        if (this.isConnected) {
            console.log('🔄 Already connected');
            return;
        }
        
        try {
            console.log('🔌 Connecting to Pipecat server...');
            
            // Create WebSocket connection for signaling
            this.websocket = new WebSocket(`${this.serverUrl}/ws`);
            
            this.websocket.onopen = () => {
                console.log('🌐 WebSocket connected');
                this.setupPeerConnection();
            };
            
            this.websocket.onmessage = (event) => {
                this.handleSignalingMessage(JSON.parse(event.data));
            };
            
            this.websocket.onerror = (error) => {
                console.error('❌ WebSocket error:', error);
                this.handleError('WebSocket connection failed');
            };
            
            this.websocket.onclose = () => {
                console.log('🔌 WebSocket disconnected');
                this.isConnected = false;
                this.notifyConnectionState('disconnected');
            };
            
        } catch (error) {
            console.error('❌ Connection failed:', error);
            this.handleError(`Connection failed: ${error.message}`);
        }
    }
    
    async setupPeerConnection() {
        try {
            // Create peer connection
            this.peerConnection = new RTCPeerConnection(this.rtcConfig);
            
            // Add local stream to peer connection
            if (this.localStream) {
                this.localStream.getTracks().forEach(track => {
                    this.peerConnection.addTrack(track, this.localStream);
                });
            }
            
            // Handle remote stream
            this.peerConnection.ontrack = (event) => {
                console.log('🎵 Received remote audio stream');
                this.remoteStream = event.streams[0];
                
                if (this.onAudioReceived) {
                    this.onAudioReceived(this.remoteStream);
                }
            };
            
            // Handle ICE candidates
            this.peerConnection.onicecandidate = (event) => {
                if (event.candidate) {
                    this.sendSignalingMessage({
                        type: 'ice-candidate',
                        candidate: event.candidate
                    });
                }
            };
            
            // Handle connection state changes
            this.peerConnection.onconnectionstatechange = () => {
                const state = this.peerConnection.connectionState;
                console.log(`🔗 WebRTC connection state: ${state}`);
                
                if (state === 'connected') {
                    this.isConnected = true;
                }
                
                this.notifyConnectionState(state);
            };
            
            // Create and send offer
            const offer = await this.peerConnection.createOffer();
            await this.peerConnection.setLocalDescription(offer);
            
            this.sendSignalingMessage({
                type: 'offer',
                offer: offer
            });
            
        } catch (error) {
            console.error('❌ Failed to setup peer connection:', error);
            this.handleError(`WebRTC setup failed: ${error.message}`);
        }
    }
    
    async handleSignalingMessage(message) {
        try {
            switch (message.type) {
                case 'answer':
                    await this.peerConnection.setRemoteDescription(message.answer);
                    console.log('✅ WebRTC answer received');
                    break;
                    
                case 'ice-candidate':
                    await this.peerConnection.addIceCandidate(message.candidate);
                    break;
                    
                case 'error':
                    this.handleError(message.message);
                    break;
                    
                default:
                    console.warn('❓ Unknown signaling message:', message);
            }
        } catch (error) {
            console.error('❌ Failed to handle signaling message:', error);
            this.handleError(`Signaling failed: ${error.message}`);
        }
    }
    
    sendSignalingMessage(message) {
        if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
            this.websocket.send(JSON.stringify(message));
        }
    }
    
    disconnect() {
        console.log('🔌 Disconnecting from Pipecat server...');
        
        if (this.peerConnection) {
            this.peerConnection.close();
            this.peerConnection = null;
        }
        
        if (this.websocket) {
            this.websocket.close();
            this.websocket = null;
        }
        
        if (this.localStream) {
            this.localStream.getTracks().forEach(track => track.stop());
            this.localStream = null;
        }
        
        this.isConnected = false;
        this.notifyConnectionState('disconnected');
    }
    
    // Utility methods
    handleError(message) {
        console.error('❌ PipecatWebRTCClient error:', message);
        if (this.onError) {
            this.onError(message);
        }
    }
    
    notifyConnectionState(state) {
        if (this.onConnectionStateChange) {
            this.onConnectionStateChange(state);
        }
    }
    
    getConnectionState() {
        if (!this.peerConnection) return 'disconnected';
        return this.peerConnection.connectionState;
    }
    
    isActive() {
        return this.isConnected && this.getConnectionState() === 'connected';
    }
}

// Export for use in main application
export default PipecatWebRTCClient;