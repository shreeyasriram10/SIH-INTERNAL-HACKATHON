import React, { useState } from 'react';
import axios from 'axios';

export default function Login({ onLogin }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    
    const params = new URLSearchParams();
    params.append('username', email);
    params.append('password', password);

    try {
      const response = await axios.post('http://localhost:8000/api/auth/login', params, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
      });
      onLogin(response.data.access_token);
    } catch (err) {
      setError('Invalid email or password. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', minHeight: '100vh', alignItems: 'center', justifyContent: 'center', background: 'var(--bg-subtle)' }}>
      <div style={{ background: 'var(--bg-surface)', padding: '40px', borderRadius: 'var(--radius-lg)', boxShadow: 'var(--shadow-xl)', width: '100%', maxWidth: '400px', border: '1px solid var(--steel-border)' }}>
        <div style={{ textAlign: 'center', marginBottom: '30px' }}>
          <img className="brand-mark" src="/loha-drishti-logo.svg" alt="Loha Drishti maritime emblem" style={{ margin: '0 auto 15px', width: '48px', height: '48px' }} />
          <h1 style={{ fontSize: '24px', margin: '0 0 5px', color: 'var(--navy-deep)' }}>LOHA DRISHTI</h1>
          <p style={{ margin: 0, fontSize: '13px', color: 'var(--steel-muted)' }}>Ministry of Steel / SAIL Logistics Platform</p>
        </div>

        {error && <div style={{ background: 'var(--red-bg)', color: 'var(--red)', padding: '10px', borderRadius: '6px', fontSize: '13px', marginBottom: '20px', textAlign: 'center', border: '1px solid var(--red-border)' }}>{error}</div>}

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
          <div className="field">
            <label>Email Address</label>
            <input 
              type="email" 
              required 
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="officer@sail.gov.in"
              style={{ padding: '10px' }}
            />
          </div>
          <div className="field">
            <label>Password</label>
            <input 
              type="password" 
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              style={{ padding: '10px' }}
            />
          </div>
          <button 
            type="submit" 
            className="btn-optimize" 
            disabled={loading}
            style={{ marginTop: '10px', justifyContent: 'center', padding: '12px' }}
          >
            {loading ? 'AUTHENTICATING...' : 'SECURE SIGN IN'}
          </button>
        </form>
        <div style={{ textAlign: 'center', marginTop: '20px', fontSize: '11px', color: 'var(--steel-muted)' }}>
          System restricted to authorized personnel only. All access is logged.
        </div>
      </div>
    </div>
  );
}
