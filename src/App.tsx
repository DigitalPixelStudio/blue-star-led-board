import { Hero } from "./components/Hero";
import { Services } from "./components/Services";
import { WhyChooseUs } from "./components/WhyChooseUs";
import { Gallery } from "./components/Gallery";
import { Testimonials } from "./components/Testimonials";
import { Contact } from "./components/Contact";
import { Footer } from "./components/Footer";
import { WhatsAppButton } from "./components/WhatsAppButton";

export default function App() {
  return (
    <main className="min-h-screen bg-[#0a0a0f] text-white font-sans overflow-x-hidden selection:bg-neon-cyan selection:text-black">
      <Hero />
      <Services />
      <WhyChooseUs />
      <Gallery />
      <Testimonials />
      <Contact />
      <Footer />
      <WhatsAppButton />
    </main>
  );
}
