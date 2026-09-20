import React, { useState } from 'react';
import { ArrowRight, CalendarDays, Coffee, Eye, EyeOff, LockKeyhole, Mail, Sparkles } from 'lucide-react';

export default function SignIn({ onSignIn }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [visible, setVisible] = useState(false);

  function submit(event) {
    event.preventDefault();
    const cleanEmail = email.trim();
    // This is the requested frontend-only sign-in. Never store or send passwords.
    onSignIn({ email: cleanEmail, name: cleanEmail.split('@')[0].replace(/[._-]/g, ' ') });
    setPassword('');
  }

  return <div className="signinLayout">
    <section className="signinStory">
      <a href="#/sign-in" className="brand signinBrand"><div className="brandMark">✦</div><div><b>Rawaj</b><span>Growth for Local Flavors</span></div></a>
      <div className="signinStoryBody">
        <span className="signinOverline"><span className="liveDot" /> MADE FOR LOCAL FAVORITES</span>
        <h1>Good food.<br />Great stories.<br /><span>Room to grow.</span></h1>
        <p>Your restaurant has something special. Turn it into a thoughtful monthly plan and content worth sharing.</p>
        <div className="signinArt" aria-hidden="true"><div className="orbit orbitOne" /><div className="orbit orbitTwo" /><div className="artCenter">✦</div><div className="artChip artChipOne"><CalendarDays size={18} /><span>A little more consistency.</span></div><div className="artChip artChipTwo"><Coffee size={18} /><span>A lot more you.</span></div></div>
      </div>
      <div className="signinStoryFoot">A clear direction for your next chapter. <Sparkles size={18} /></div>
    </section>
    <main className="signinMain">
      <div className="signinCard">
        <div className="signinWelcome"><div className="brandMark">✦</div><span className="pill">Your growth workspace</span></div>
        <div className="eyebrow">LET’S MAKE SOMETHING GOOD</div>
        <h2>Welcome to Rawaj.</h2>
        <p className="signinIntro">One home for your strategy, your calendar, and your next great idea.</p>
        <form onSubmit={submit} className="signinForm">
          <label htmlFor="signin-email">Email</label><div className="inputWithIcon"><Mail size={18} /><input id="signin-email" type="email" autoComplete="username" value={email} onChange={e => setEmail(e.target.value)} placeholder="you@example.com" required maxLength={255} /></div>
          <label htmlFor="signin-password">Password</label><div className="inputWithIcon"><LockKeyhole size={18} /><input id="signin-password" type={visible ? 'text' : 'password'} autoComplete="off" value={password} onChange={e => setPassword(e.target.value)} placeholder="Enter a demo password" required minLength={6} /><button type="button" aria-label={visible ? 'Hide password' : 'Show password'} onClick={() => setVisible(!visible)}>{visible ? <EyeOff size={18} /> : <Eye size={18} />}</button></div>
          <button className="primary signinSubmit" type="submit">Sign in <ArrowRight size={18} /></button>
        </form>
        <div className="previewNote"><b>Preview access</b><p>This sign-in is a demo. Use any email and a demo password of 6+ characters. Your password is never sent or saved.</p><button type="button" onClick={() => { setEmail('demo@rawaj.example'); setPassword('rawaj-demo'); }}>Fill demo details <ArrowRight size={13} /></button></div>
      </div>
      <p className="signinFooter">Built with care for restaurants and cafés.</p>
    </main>
  </div>;
}
