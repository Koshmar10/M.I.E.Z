import React, { useState, useEffect } from 'react';
import { FiUser, FiLock, FiMail, FiShield, FiBriefcase, FiCheck, FiAlertCircle } from 'react-icons/fi';
import { authApi } from '../../api/auth';
import { api, errorMessage } from '../../api/client';

export default function SettingsPage() {
  const [profileData, setProfileData] = useState({
    first_name: '',
    last_name: '',
    phone: '',
    address: '',
    email: '',
    role: '',
    department_name: ''
  });

  const [passwordData, setPasswordData] = useState({
    current_password: '',
    new_password: '',
    confirm_password: ''
  });

  const [profileStatus, setProfileStatus] = useState({ type: '', message: '' });
  const [passwordStatus, setPasswordStatus] = useState({ type: '', message: '' });

  const [loading, setLoading] = useState(true);
  const [savingProfile, setSavingProfile] = useState(false);
  const [savingPassword, setSavingPassword] = useState(false);

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        const data = await authApi.me();
        setProfileData({
          first_name: data.first_name,
          last_name: data.last_name,
          phone: data.phone,
          address: data.address,
          email: data.email,
          role: data.role,
          department_name: data.department_name ?? 'N/A'
        });
      } catch (err) {
        console.error('Failed to load profile', err);
      } finally {
        setLoading(false);
      }
    };
    void fetchProfile();
  }, []);

  const handleProfileSubmit = async (e: React.SyntheticEvent<HTMLFormElement>) => {
    e.preventDefault();
    setSavingProfile(true);
    setProfileStatus({ type: '', message: '' });

    try {
      await api.patch('/api/auth/me/', {
        first_name: profileData.first_name,
        last_name: profileData.last_name,
        phone: profileData.phone,
        address: profileData.address
      });
      setProfileStatus({ type: 'success', message: 'Profile updated successfully!' });
    } catch (err) {
      setProfileStatus({ type: 'error', message: errorMessage(err, 'Failed to update profile.') });
    } finally {
      setSavingProfile(false);
    }
  };

  const handlePasswordSubmit = async (e: React.SyntheticEvent<HTMLFormElement>) => {
    e.preventDefault();
    setPasswordStatus({ type: '', message: '' });

    if (passwordData.new_password !== passwordData.confirm_password) {
      setPasswordStatus({ type: 'error', message: 'New passwords do not match.' });
      return;
    }

    if (passwordData.new_password.length < 8) {
      setPasswordStatus({ type: 'error', message: 'Password must be at least 8 characters long.' });
      return;
    }

    setSavingPassword(true);
    try {
      await api.post('/api/auth/change-password/', {
        current_password: passwordData.current_password,
        new_password: passwordData.new_password
      });
      setPasswordStatus({ type: 'success', message: 'Password changed successfully!' });
      setPasswordData({ current_password: '', new_password: '', confirm_password: '' });
    } catch (err) {
      setPasswordStatus({ type: 'error', message: errorMessage(err, 'Failed to change password.') });
    } finally {
      setSavingPassword(false);
    }
  };

  const inputClass =
    'w-full bg-[var(--input-background)] border border-[var(--border)] text-[var(--foreground)] text-sm rounded-xl focus:ring-2 focus:ring-[var(--primary)]/20 focus:border-[var(--primary)] block p-3 outline-none transition-all';

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--primary)]"></div>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6 pb-12">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-[var(--foreground)] tracking-tight">Account Settings</h1>
        <p className="text-[var(--muted-foreground)] mt-1">Manage your personal information and security preferences.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Column: Read-only info & Profile Form */}
        <div className="lg:col-span-2 space-y-8">

          {/* Profile Form */}
          <div className="bg-[var(--card)] text-[var(--card-foreground)] rounded-2xl border border-[var(--border)] p-6 sm:p-8">
            <div className="flex items-center gap-3 mb-6">
              <div className="p-2.5 bg-[var(--primary)]/10 text-[var(--primary)] rounded-xl">
                <FiUser size={20} />
              </div>
              <h2 className="text-lg font-semibold text-[var(--card-foreground)]">Personal Information</h2>
            </div>

            {profileStatus.message && (
              <div className={`mb-6 p-4 rounded-xl flex items-start gap-3 text-sm font-medium ${profileStatus.type === 'success' ? 'bg-emerald-50 text-emerald-700 border border-emerald-100' : 'bg-[var(--primary)]/10 text-[var(--primary)] border border-[var(--primary)]/20'}`}>
                {profileStatus.type === 'success' ? <FiCheck size={18} className="mt-0.5" /> : <FiAlertCircle size={18} className="mt-0.5" />}
                {profileStatus.message}
              </div>
            )}

            <form onSubmit={(e) => void handleProfileSubmit(e)} className="space-y-5">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                <div>
                  <label className="block text-sm font-medium text-[var(--foreground)] mb-1.5">First Name</label>
                  <input
                    type="text"
                    value={profileData.first_name}
                    onChange={e => setProfileData({...profileData, first_name: e.target.value})}
                    className={inputClass}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-[var(--foreground)] mb-1.5">Last Name</label>
                  <input
                    type="text"
                    value={profileData.last_name}
                    onChange={e => setProfileData({...profileData, last_name: e.target.value})}
                    className={inputClass}
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-[var(--foreground)] mb-1.5">Phone Number</label>
                <input
                  type="text"
                  value={profileData.phone}
                  onChange={e => setProfileData({...profileData, phone: e.target.value})}
                  className={inputClass}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-[var(--foreground)] mb-1.5">Home Address</label>
                <textarea
                  rows={3}
                  value={profileData.address}
                  onChange={e => setProfileData({...profileData, address: e.target.value})}
                  className={`${inputClass} resize-none`}
                />
              </div>

              <div className="pt-4 flex justify-end border-t border-[var(--border)] mt-6">
                <button
                  type="submit"
                  disabled={savingProfile}
                  className="px-6 py-2.5 text-[var(--primary-foreground)] bg-[var(--primary)] hover:opacity-90 rounded-xl text-sm font-semibold transition-opacity disabled:opacity-70 flex items-center gap-2"
                >
                  {savingProfile ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
            </form>
          </div>

          {/* Password Form */}
          <div className="bg-[var(--card)] text-[var(--card-foreground)] rounded-2xl border border-[var(--border)] p-6 sm:p-8">
            <div className="flex items-center gap-3 mb-6">
              <div className="p-2.5 bg-[var(--primary)]/10 text-[var(--primary)] rounded-xl">
                <FiLock size={20} />
              </div>
              <h2 className="text-lg font-semibold text-[var(--card-foreground)]">Change Password</h2>
            </div>

            {passwordStatus.message && (
              <div className={`mb-6 p-4 rounded-xl flex items-start gap-3 text-sm font-medium ${passwordStatus.type === 'success' ? 'bg-emerald-50 text-emerald-700 border border-emerald-100' : 'bg-[var(--primary)]/10 text-[var(--primary)] border border-[var(--primary)]/20'}`}>
                {passwordStatus.type === 'success' ? <FiCheck size={18} className="mt-0.5" /> : <FiAlertCircle size={18} className="mt-0.5" />}
                {passwordStatus.message}
              </div>
            )}

            <form onSubmit={(e) => void handlePasswordSubmit(e)} className="space-y-5">
              <div>
                <label className="block text-sm font-medium text-[var(--foreground)] mb-1.5">Current Password</label>
                <input
                  type="password"
                  required
                  value={passwordData.current_password}
                  onChange={e => setPasswordData({...passwordData, current_password: e.target.value})}
                  className={inputClass}
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                <div>
                  <label className="block text-sm font-medium text-[var(--foreground)] mb-1.5">New Password</label>
                  <input
                    type="password"
                    required
                    value={passwordData.new_password}
                    onChange={e => setPasswordData({...passwordData, new_password: e.target.value})}
                    className={inputClass}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-[var(--foreground)] mb-1.5">Confirm New Password</label>
                  <input
                    type="password"
                    required
                    value={passwordData.confirm_password}
                    onChange={e => setPasswordData({...passwordData, confirm_password: e.target.value})}
                    className={inputClass}
                  />
                </div>
              </div>

              <div className="pt-4 flex justify-end border-t border-[var(--border)] mt-6">
                <button
                  type="submit"
                  disabled={savingPassword}
                  className="px-6 py-2.5 text-[var(--primary-foreground)] bg-[var(--primary)] hover:opacity-90 rounded-xl text-sm font-semibold transition-opacity disabled:opacity-70 flex items-center gap-2"
                >
                  {savingPassword ? 'Updating...' : 'Update Password'}
                </button>
              </div>
            </form>
          </div>
        </div>

        {/* Right Column: Read-Only Overview */}
        <div className="space-y-6">
          <div className="bg-[var(--card)] text-[var(--card-foreground)] rounded-2xl border border-[var(--border)] p-6">
            <h3 className="text-[13px] font-semibold text-[var(--muted-foreground)] uppercase tracking-wider mb-6">Account Details</h3>

            <div className="space-y-5">
              <div className="flex items-start gap-4">
                <div className="p-2.5 bg-[var(--muted)] text-[var(--muted-foreground)] rounded-xl mt-0.5">
                  <FiMail size={18} />
                </div>
                <div>
                  <p className="text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">Email Address</p>
                  <p className="text-sm font-semibold text-[var(--card-foreground)] mt-0.5 break-all">{profileData.email}</p>
                </div>
              </div>

              <div className="flex items-start gap-4">
                <div className="p-2.5 bg-[var(--muted)] text-[var(--muted-foreground)] rounded-xl mt-0.5">
                  <FiShield size={18} />
                </div>
                <div>
                  <p className="text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">Role / Access</p>
                  <p className="text-sm font-semibold text-[var(--card-foreground)] mt-0.5">{profileData.role}</p>
                </div>
              </div>

              <div className="flex items-start gap-4">
                <div className="p-2.5 bg-[var(--muted)] text-[var(--muted-foreground)] rounded-xl mt-0.5">
                  <FiBriefcase size={18} />
                </div>
                <div>
                  <p className="text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">Department</p>
                  <p className="text-sm font-semibold text-[var(--card-foreground)] mt-0.5">{profileData.department_name}</p>
                </div>
              </div>
            </div>

            <div className="mt-8 pt-6 border-t border-[var(--border)]">
              <p className="text-xs text-[var(--muted-foreground)] leading-relaxed">
                Some details like your email and role are managed by HR. If you need to update them, please open an IT or HR ticket.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
