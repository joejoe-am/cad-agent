import React from "react";
import { ArrowUpRight, Box, ShieldCheck, Sparkles, Wrench } from "lucide-react";

const STARTERS = [
  {
    title: "Design a part",
    icon: Sparkles,
    text: "Help me design a new part. Let’s discuss its dimensions and intended use first.",
  },
  {
    title: "Work in PowerMill",
    icon: Wrench,
    text: "I want to work only in PowerMill. Inspect the current project before making changes.",
  },
  {
    title: "Refine a model",
    icon: Box,
    text: "I want to refine an existing SolidWorks part using reference images. Help me plan the changes.",
  },
];

export default function Welcome({ onStarter }) {
  return (
    <section className="welcome">
      <div className="welcome-mark">
        <Box size={34} />
      </div>
      <div className="eyebrow">YOUR NEXT IDEA STARTS HERE</div>
      <h1>
        From a thought
        <br />
        to something tangible.
      </h1>
      <p>
        Design, refine, and inspect with an assistant that
        <br />
        remembers your project and chooses the right tools.
      </p>
      <div className="starters">
        {STARTERS.map(({ title, icon: Icon, text }) => (
          <button key={title} onClick={() => onStarter(text)}>
            <span>
              <Icon size={19} />
            </span>
            {title}
            <ArrowUpRight size={15} />
          </button>
        ))}
      </div>
      <div className="welcome-note">
        <ShieldCheck size={15} /> Conversation history is saved on this
        computer.
      </div>
    </section>
  );
}
