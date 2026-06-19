export function Footer() {
  return (
    <footer className="bg-[#050508] pt-16 pb-8 border-t border-white/5">
      <div className="max-w-6xl mx-auto px-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-12 mb-12">
          
          <div>
            <h2 className="text-2xl font-black uppercase mb-4 tracking-wider text-white">
              Blue Star <span className="text-neon-cyan text-glow-cyan">LED</span>
            </h2>
            <p className="text-gray-400 font-light text-sm leading-relaxed mb-6">
              Bangalore's trusted signage partner. We craft brilliant LED, Neon, and Acrylic boards for businesses that want to be seen.
            </p>
            <div className="text-xs text-gray-500 uppercase tracking-widest">
              Est. 2014 • 10 Years Excellence
            </div>
          </div>

          <div>
            <h4 className="text-lg font-bold uppercase tracking-wider text-white mb-4">Quick Links</h4>
            <ul className="space-y-3 text-gray-400 font-light text-sm">
              <li><a href="#services" className="hover:text-neon-cyan transition-colors">Our Services</a></li>
              <li><a href="#portfolio" className="hover:text-neon-magenta transition-colors">Portfolio</a></li>
              <li><a href="#contact" className="hover:text-neon-blue transition-colors">Contact Us</a></li>
            </ul>
          </div>

          <div>
            <h4 className="text-lg font-bold uppercase tracking-wider text-white mb-4">Contact</h4>
            <ul className="space-y-3 text-gray-400 font-light text-sm">
              <li>MD Faheem</li>
              <li>+91 97433 41423</li>
              <li>No 235, Jain Temple Road,</li>
              <li>Shivajinagar, Bangalore 560051</li>
            </ul>
          </div>

        </div>

        <div className="pt-8 border-t border-white/10 text-center flex flex-col md:flex-row justify-between items-center gap-4">
          <p className="text-gray-500 text-sm">
            © {new Date().getFullYear()} Blue Star LED Board. All rights reserved.
          </p>
          <div className="text-gray-500 text-sm">
            Made with <span className="text-neon-magenta">glow</span> in Bangalore
          </div>
        </div>
      </div>
    </footer>
  );
}
