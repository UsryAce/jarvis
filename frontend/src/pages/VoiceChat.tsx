import React, { useState, useRef, useEffect } from 'react'
import { useVoiceStore } from '../store/useVoiceStore'
import { useSystemStore } from '../store/useSystemStore'

export const VoiceChat: React.FC = () => {
  const {
    isListening,
    isSpeaking,
    isProcessing,
    wakeWordDetected,
    confidence,
    audioData,
    startListening,
    stopListening,
    speak,
    conversationHistory,
  } = useVoiceStore()

  const { cpuUsage, memoryUsage, gpu } = useSystemStore()

  const [inputText, setInputText] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [conversationHistory])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!inputText.trim()) return

    await speak(inputText)
    setInputText('')
  }

  const handleVoiceToggle = () => {
    if (isListening) {
      stopListening()
    } else {
      startListening()
    }
  }

  return (
    <React.Fragment>
    <div style={{
      width: '100%',
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      background: 'linear-gradient(135deg, #050510 0%, #0a0a1a 100%)',
      fontFamily: "'JetBrains Mono', monospace",
      color: '#e6e8f0',
      overflow: 'hidden'
    }}>
      {/* Header */}
      <header style={{
        padding: '20px 40px',
        background: 'rgba(5, 5, 15, 0.95)',
        backdropFilter: 'blur(20px)',
        borderBottom: '1px solid rgba(0, 255, 255, 0.2)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
          <h1 style={{
            fontSize: '28px',
            fontWeight: '700',
            letterSpacing: '4px',
            background: 'linear-gradient(135deg, #00ffff, #ff00ff, #ff6b00)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            backgroundClip: 'text'
          }}>VOICE CHAT</h1>

          <div style={{ display: 'flex', alignItems: 'center', gap: '15px', fontSize: '12px', opacity: 0.7 }}>
            <span>Model: <strong style={{ color: '#00ffff' }}>Nemotron 3 Ultra</strong></span>
            <span>|</span>
            <span>STT: <strong style={{ color: '#ff00ff' }}>Whisper Base</strong></span>
            <span>|</span>
            <span>TTS: <strong style={{ color: '#ff6b00' }}>Edge Neural</strong></span>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            background: wakeWordDetected ? 'rgba(255, 0, 255, 0.2)' : (isListening ? 'rgba(0, 255, 0, 0.2)' : (isSpeaking ? 'rgba(255, 107, 0, 0.2)' : 'rgba(255, 0, 255, 0.1)')),
            border: `1px solid ${wakeWordDetected ? '#ff00ff' : (isListening ? '#00ff00' : (isSpeaking ? '#ff6b00' : '#ff00ff'))}`,
            borderRadius: '8px',
            padding: '8px 16px'
          }}>
            <span style={{
              width: '10px',
              height: '10px',
              borderRadius: '50%',
              background: wakeWordDetected ? '#ff00ff' : (isListening ? '#00ff00' : (isSpeaking ? '#ff6b00' : '#666')),
              boxShadow: wakeWordDetected ? '0 0 10px #ff00ff' : (isListening ? '0 0 10px #00ff00' : (isSpeaking ? '0 0 10px #ff6b00' : 'none')),
              animation: wakeWordDetected ? 'pulse 0.5s infinite' : (isListening || isSpeaking ? 'pulse 1s infinite' : 'none')
            }} />
            <span style={{
              fontWeight: '600',
              textTransform: 'uppercase',
              letterSpacing: '1px',
              color: wakeWordDetected ? '#ff00ff' : (isListening ? '#00ff00' : (isSpeaking ? '#ff6b00' : '#888'))
            }}>
              {wakeWordDetected ? 'WAKE WORD' : (isListening ? 'LISTENING' : (isSpeaking ? 'SPEAKING' : (isProcessing ? 'PROCESSING' : 'STANDBY')))}
            </span>
          </div>

          <div style={{
            fontSize: '11px',
            opacity: 0.6,
            fontFamily: "'JetBrains Mono', monospace",
            color: '#888'
          }}>
            Confidence: {(confidence * 100).toFixed(0)}%
          </div>
        </div>
      </header>

      {/* Chat Area */}
      <main style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        padding: '20px 40px',
        overflow: 'hidden'
      }}>
        {/* Conversation History */}
        <div style={{
          flex: 1,
          overflowY: 'auto',
          padding: '20px',
          display: 'flex',
          flexDirection: 'column',
          gap: '16px'
        }}>
          {conversationHistory.length === 0 && (
            <div style={{
              textAlign: 'center',
              padding: '60px 20px',
              opacity: 0.4
            }}>
              <div style={{ fontSize: '48px', marginBottom: '16px' }}>🤖</div>
              <h2 style={{
                fontWeight: '300',
                marginBottom: '8px',
                background: 'linear-gradient(135deg, #00ffff, #ff00ff)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent'
              }}>
                JARVIS Ready
              </h2>
              <p style={{ opacity: 0.5, fontSize: '14px' }}>
                Say "Jarvis" or type a message to begin
              </p>
            </div>
          )}

            {conversationHistory.map((msg, i) => (
              <div key={i} style={{
                display: 'flex',
                flexDirection: 'column',
                maxWidth: '80%',
                alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
                animation: 'fadeInUp 0.3s ease-out'
              }}>
                <div style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '12px',
                  marginBottom: '4px'
                }}>
                  <div style={{
                    width: '36px',
                    height: '36px',
                    borderRadius: '50%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0,
                    background: msg.role === 'user' ? 'linear-gradient(135deg, #00ffff, #0088ff)' : 'linear-gradient(135deg, #ff00ff, #8800ff)',
                    color: '#000',
                    fontWeight: 'bold',
                    fontSize: '14px'
                  }}>
                    {msg.role === 'user' ? 'U' : 'J'}
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{
                      fontSize: '10px',
                      opacity: 0.5,
                      marginBottom: '4px',
                      textTransform: 'uppercase',
                      letterSpacing: '1px',
                      color: msg.role === 'user' ? '#00ffff' : '#ff00ff'
                    }}>
                      {msg.role === 'user' ? 'YOU' : 'JARVIS'} • {new Date(msg.timestamp).toLocaleTimeString()}
                    </div>
                    <div style={{
                      padding: '12px 16px',
                      background: msg.role === 'user' ? 'rgba(0, 255, 255, 0.1)' : 'rgba(255, 0, 255, 0.1)',
                      border: `1px solid ${msg.role === 'user' ? 'rgba(0, 255, 255, 0.3)' : 'rgba(255, 0, 255, 0.3)'}`,
                      borderRadius: '12px',
                      borderTopRightRadius: msg.role === 'user' ? '0' : '12px',
                      borderTopLeftRadius: msg.role === 'user' ? '12px' : '0',
                      wordWrap: 'break-word',
                      lineHeight: 1.5
                    }}>
                      {msg.content}
                    </div>
                    {msg.confidence && (
                      <div style={{
                        fontSize: '9px',
                        opacity: 0.4,
                        marginTop: '4px',
                        fontFamily: "'JetBrains Mono', monospace",
                        color: '#888'
                      }}>
                        Confidence: {(msg.confidence * 100).toFixed(0)}%
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>

          {/* Audio Visualizer */}
          {(isListening || isSpeaking) && (
            <div style={{
              height: '60px',
              display: 'flex',
              alignItems: 'flex-end',
              justifyContent: 'center',
              gap: '2px',
              padding: '0 20px'
            }}>
              {Array.from({ length: 64 }).map((_, i) => (
                <div key={i} style={{
                  width: '3px',
                  height: Math.max(4, (audioData[i * 4] || 0) / 255 * 50),
                  background: `hsl(${180 + i * 3}, 100%, 50%)`,
                  borderRadius: '2px',
                  margin: '0 1px',
                  transition: 'height 0.05s ease',
                  opacity: isListening ? 1 : (isSpeaking ? 0.8 : 0.3)
                }} />
              ))}
            </div>
          )}

          {/* Input Area */}
          <div style={{
            padding: '20px',
            background: 'rgba(5, 5, 15, 0.8)',
            backdropFilter: 'blur(20px)',
            borderTop: '1px solid rgba(0, 255, 255, 0.2)',
            borderRadius: '16px 16px 0 0'
          }}>
            <form onSubmit={handleSubmit} style={{ display: 'flex', gap: '15px', alignItems: 'center' }}>
              <input
                type="text"
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                placeholder={isListening ? 'Listening...' : (isProcessing ? 'Processing...' : 'Type a message or press Space to speak...')}
                style={{
                  flex: 1,
                  padding: '16px 20px',
                  background: 'rgba(0, 0, 0, 0.5)',
                  border: `1px solid ${isListening ? '#00ff00' : (isProcessing ? '#ff6b00' : 'rgba(0, 255, 255, 0.3)')}`,
                  borderRadius: '12px',
                  color: '#fff',
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: '14px',
                  outline: 'none',
                  transition: 'all 0.2s'
                }}
                onFocus={(e) => e.currentTarget.style.borderColor = '#00ffff'}
                onBlur={(e) => e.currentTarget.style.borderColor = 'rgba(0, 255, 255, 0.3)'}
                disabled={isProcessing}
              />

              <button
                type="submit"
                disabled={!inputText.trim() || isProcessing}
                style={{
                  padding: '16px 28px',
                  background: 'linear-gradient(135deg, #00ffff, #0088ff)',
                  border: 'none',
                  color: '#000',
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: '12px',
                  fontWeight: '600',
                  textTransform: 'uppercase',
                  letterSpacing: '1px',
                  borderRadius: '12px',
                  cursor: inputText.trim() && !isProcessing ? 'pointer' : 'not-allowed',
                  opacity: inputText.trim() && !isProcessing ? 1 : 0.5,
                  transition: 'all 0.2s',
                  whiteSpace: 'nowrap'
                }}
                onMouseEnter={(e) => {
                  if (!isProcessing && inputText.trim()) {
                    e.currentTarget.style.boxShadow = '0 0 30px rgba(0, 255, 255, 0.5)'
                    e.currentTarget.style.transform = 'translateY(-2px)'
                  }
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.boxShadow = 'none'
                  e.currentTarget.style.transform = 'translateY(0)'
                }}
              >
                {isProcessing ? '⚙ PROCESSING...' : 'SEND'}
              </button>

              <button
                type="button"
                onClick={handleVoiceToggle}
                disabled={isProcessing}
                style={{
                  width: '56px',
                  height: '56px',
                  borderRadius: '50%',
                  background: isListening
                    ? 'linear-gradient(135deg, #ff0000, #ff6b00)'
                    : (isSpeaking ? 'linear-gradient(135deg, #ff6b00, #ff00ff)' : 'linear-gradient(135deg, #00ffff, #0088ff)'),
                  border: 'none',
                  color: '#fff',
                  cursor: isProcessing ? 'not-allowed' : 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  transition: 'all 0.2s',
                  boxShadow: isListening ? '0 0 30px #ff0000' : (isSpeaking ? '0 0 30px #ff6b00' : '0 0 30px rgba(0, 255, 255, 0.4)'),
                  opacity: isProcessing ? 0.5 : 1
                }}
                onMouseEnter={(e) => {
                  if (!isProcessing) {
                    e.currentTarget.style.transform = 'scale(1.05)'
                    e.currentTarget.style.boxShadow = isListening ? '0 0 40px #ff0000' : (isSpeaking ? '0 0 40px #ff6b00' : '0 0 40px rgba(0, 255, 255, 0.6)')
                  }
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.transform = 'scale(1)'
                  e.currentTarget.style.boxShadow = isListening ? '0 0 30px #ff0000' : (isSpeaking ? '0 0 30px #ff6b00' : '0 0 30px rgba(0, 255, 255, 0.4)')
                }}
              >
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  {isSpeaking ? (
                    <polygon points="5 3 19 12 5 21 5 3" />
                  ) : isListening ? (
                    <>
                      <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                      <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                      <line x1="12" y1="19" x2="12" y2="22" />
                      <line x1="8" y1="22" x2="16" y2="22" />
                    </>
                  ) : (
                    <>
                      <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                      <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                      <line x1="12" y1="19" x2="12" y2="22" />
                      <line x1="8" y1="22" x2="16" y2="22" />
                    </>
                  )}
                </svg>
              </button>
            </form>

            {/* Audio Waveform Display */}
            {(isListening || isSpeaking) && audioData && (
              <div style={{
                height: '50px',
                display: 'flex',
                alignItems: 'flex-end',
                justifyContent: 'center',
                gap: '2px',
                padding: '0 20px',
                marginTop: '10px'
              }}>
                {Array.from({ length: 128 }).map((_, i) => (
                  <div key={i} style={{
                    width: '3px',
                    height: Math.max(3, (audioData[i * 2] || 0) / 255 * 40),
                    background: `hsl(${180 + i * 1.5}, 100%, 50%)`,
                    borderRadius: '2px',
                    margin: '0 1px',
                    transition: 'height 0.05s ease',
                    opacity: isListening ? 1 : 0.7
                  }} />
                ))}
              </div>
            )}
          </div>
        </main>

        {/* Status Bar */}
        <footer style={{
          padding: '12px 40px',
          background: 'rgba(5, 5, 15, 0.9)',
          backdropFilter: 'blur(20px)',
          borderTop: '1px solid rgba(0, 255, 255, 0.1)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          fontSize: '11px',
          color: '#888',
          fontFamily: "'JetBrains Mono', monospace"
        }}>
          <div style={{ display: 'flex', gap: '20px' }}>
            <span>JARVIS v1.0.0</span>
            <span>|</span>
            <span>Nemotron 3 Ultra + GLM-5.2 + Kimi K2.6</span>
            <span>|</span>
            <span>Voice: Edge TTS + Whisper</span>
            <span>|</span>
            <span>Vision: MediaPipe + YOLOv8</span>
          </div>
          <div style={{ display: 'flex', gap: '20px' }}>
            <span>CPU: {cpuUsage.toFixed(1)}%</span>
            <span>|</span>
            <span>RAM: {memoryUsage.toFixed(1)}%</span>
            <span>|</span>
            <span>GPU: {gpu[0]?.usage.toFixed(1) || 0}%</span>
          </div>
        </footer>
      </div>

      <style dangerouslySetInnerHTML={{ __html: `
          @keyframes fadeInUp {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
          }

          @keyframes pulse {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.7; transform: scale(1.05); }
          }

          ::-webkit-scrollbar { width: 6px; }
          ::-webkit-scrollbar-track { background: #050510; }
          ::-webkit-scrollbar-thumb {
            background: linear-gradient(180deg, #00ffff, #ff00ff);
            border-radius: 3px;
          }
          ::-webkit-scrollbar-thumb:hover {
            background: linear-gradient(180deg, #ff00ff, #ff6b00);
          }
        ` }} />
    </React.Fragment>
  )
}

export default VoiceChat
