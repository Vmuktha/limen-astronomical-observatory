'use client'

import Link from 'next/link'
import { ArrowDown, ArrowRight, Atom, AudioLines, BookOpen, CircleDot, Crosshair, ScanSearch } from 'lucide-react'
import { motion, useReducedMotion } from 'framer-motion'

const destinations = [
  { number: '01', title: 'Observatory', text: 'Locate the 200 real DESI candidates across the sky, plotted at their measured coordinates.', icon: CircleDot, active: true },
  { number: '02', title: 'Galaxy Atlas', text: 'Browse the Legacy Survey DR10 g, r, z observations behind each investigation.', icon: ScanSearch },
  { number: '03', title: 'Evidence Laboratory', text: 'Interrogate spectra, model fits, residuals, imaging, and quality evidence together.', icon: AudioLines },
  { number: '04', title: 'Robustness Studio', text: 'Examine the actual Phase 5 perturbation experiments and their measured outcomes.', icon: Atom },
  { number: '05', title: 'Research & Methodology', text: 'Follow the scientific pipeline, experimental design, findings, and limitations.', icon: BookOpen },
  { number: '06', title: 'Candidate dossier', text: 'Carry one candidate’s evidence consistently from the atlas or sky into its investigation.', icon: Crosshair },
]

export default function Home() {
  const reduceMotion = useReducedMotion()

  return (
    <main className="limen-home">
      <section className="hero-shell" aria-labelledby="hero-title">
        <div className="hero-image" aria-hidden="true" />
        <div className="hero-vignette" aria-hidden="true" />
        <div className="hero-stars" aria-hidden="true" />
        <header className="site-nav">
          <Link href="/" className="brand" aria-label="LIMEN home">
            <span className="brand-mark"><span /></span>
            <span>LIMEN<small>ASTRONOMICAL INVESTIGATION</small></span>
          </Link>
          <nav aria-label="Main navigation">
            <a href="#investigation">The investigation</a>
            <a href="#research">Research</a>
            <Link className="nav-enter" href="/observatory">Enter observatory <ArrowRight aria-hidden="true" /></Link>
          </nav>
        </header>

        <div className="hero-content">
          <motion.div initial={reduceMotion ? false : { opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8 }}>
            <p className="eyebrow"><span className="eyebrow-line" /> A MULTIMODAL ASTRONOMICAL INVESTIGATION</p>
            <h1 id="hero-title">Where the<br /><em>unexplained</em> begins.</h1>
            <p className="hero-copy">The universe is full of things we can detect but cannot yet explain. LIMEN brings spectra, galaxy images, and physical models together to investigate what lies beyond the familiar.</p>
            <div className="hero-actions">
              <Link href="/observatory" className="button-primary">Enter the Observatory <ArrowRight aria-hidden="true" /></Link>
              <a href="#research" className="button-quiet">Explore the research <span>↓</span></a>
            </div>
          </motion.div>
        </div>

        <div className="hero-caption"><span>DESI DR1 × LEGACY SURVEY DR10</span><span>200 CANDIDATES · ONE INVESTIGATION</span></div>
        <a href="#investigation" className="scroll-cue" aria-label="Scroll to explore"><span /><ArrowDown aria-hidden="true" /></a>
      </section>

      <section className="manifesto" id="research">
        <div className="section-kicker"><span>01 / THE QUESTION</span><span>AN OPEN INVESTIGATION</span></div>
        <div className="manifesto-grid">
          <h2>Not just what is unusual.<br /><em>What can’t we explain?</em></h2>
          <div className="manifesto-copy"><p>Rare astronomical observations can be unusual for many reasons. LIMEN brings independent kinds of evidence into one careful investigation—without mistaking a model score for a discovery.</p><p className="manifesto-pull">Don’t just detect the anomaly.<br /><span>Interrogate it.</span></p></div>
        </div>
      </section>

      <section className="investigation-section" id="investigation">
        <div className="section-kicker"><span>02 / ONE CONNECTED PLATFORM</span><span>BUILT AROUND THE CANDIDATE</span></div>
        <div className="section-heading"><h2>Every clue, in context.</h2><p>Move from the measured sky position to the underlying observations, evidence, and experimental record. A selected candidate is the thread that connects every view.</p></div>
        <div className="destination-grid">
          {destinations.map(({ number, title, text, icon: Icon, active }) => (
            <article key={number} className={`destination ${active ? 'destination-active' : ''}`}>
              <div className="destination-top"><span>{number}</span><Icon aria-hidden="true" /></div>
              <h3>{title}</h3><p>{text}</p>
              {active && <Link href="/observatory" aria-label="Open the Observatory">Open investigation <ArrowRight aria-hidden="true" /></Link>}
            </article>
          ))}
        </div>
      </section>

      <section className="data-note">
        <span className="data-orbit" aria-hidden="true" />
        <div><p className="eyebrow">EVIDENCE BEFORE INTERPRETATION</p><h2>Real observations.<br /><em>Careful conclusions.</em></h2></div>
        <p className="data-copy">The existing 200 Legacy Survey DR10 grz cutouts remain the scientific inputs. Candidate identifiers, coordinates, spectra, and experiment outputs come from the project’s research data—not generated examples.</p>
      </section>

      <footer className="site-footer"><Link href="/" className="footer-wordmark">LIMEN</Link><span>Multimodal Astronomical Outlier Discovery through Representation Learning, Physics-Model Discrepancy, and Cross-Survey Validation.</span><Link href="/observatory">Begin the investigation <ArrowRight aria-hidden="true" /></Link></footer>
    </main>
  )
}
