import re
from pathlib import Path
from engine import RLColorizer

BASE_DIR = Path(__file__).resolve().parent
ACC_DIR = BASE_DIR / "accessibility_logs"
OUT_DIR = BASE_DIR / "output_accessibility"
OUT_DIR.mkdir(parents=True, exist_ok=True)

colorizer = RLColorizer()

files = sorted(list(ACC_DIR.glob("*.txt")))
print(f"Total accessibility logs to audit: {len(files)}")

# Global audit collectors
uncolored_candidates = {} # pattern -> list of occurrences
rule_usage = {}
total_lines_all = 0
total_colored_all = 0

for f in files:
    raw_text = f.read_text(encoding='utf-8')
    lines = raw_text.splitlines()
    
    colorized_html = colorizer.colorize_text(raw_text)
    (OUT_DIR / f"{f.stem}_colored.html").write_text(colorized_html, encoding='utf-8')
    
    # Analyze lines
    file_colored = 0
    file_uncolored = 0
    
    for line in lines:
        clean = line.strip()
        if not clean:
            continue
        total_lines_all += 1
        
        styled = colorizer.colorize_line(clean)
        
        # Check if colored (has style other than just default silver)
        is_default = styled.startswith('<span style="color: #c0c0c0;">') and styled.count('<span') == 1
        if is_default:
            file_uncolored += 1
            # Check if this line looks like it SHOULD be colored
            # Look for combat words, spells, damage, commands, exp, movement, prompt
            lower = clean.lower()
            if any(w in lower for w in [
                'golpea', 'corta', 'desgarra', 'perfora', 'clava', 'muerde', 'raja', 'patea',
                'aplasta', 'hechizo', 'cántico', 'formular', 'invocas', 'salidas', 'pvs:',
                'obtienes', 'esquiva', 'bloquea', 'parar', 'muerto', 'daño', 'alcanza',
                'lanza', 'proyectil', 'furia', 'estocada', 'puñetazo', 'patada'
            ]):
                # Potential missed line
                # Truncate to category signature
                sig = clean[:60]
                uncolored_candidates.setdefault(sig, []).append((f.stem, clean))
        else:
            file_colored += 1
            total_colored_all += 1
            
    pct = (file_colored / (file_colored + file_uncolored) * 100) if (file_colored + file_uncolored) else 0
    print(f"[{f.stem}] Lines: {file_colored + file_uncolored:4d} | Colored: {file_colored:4d} ({pct:5.1f}%) | Uncolored: {file_uncolored:4d}")

print("\n" + "=" * 70)
print(f"GLOBAL AUDIT SUMMARY:")
print(f"Total lines analyzed: {total_lines_all}")
print(f"Total colored lines:  {total_colored_all} ({total_colored_all/total_lines_all*100:.1f}%)")
print(f"Total uncolored:      {total_lines_all - total_colored_all} ({(total_lines_all - total_colored_all)/total_lines_all*100:.1f}%)")
print("=" * 70)

print(f"\nPOTENTIAL MISSED COMBAT/SPELL/SYSTEM LINES ({len(uncolored_candidates)} unique signatures):")
# Sort by frequency
sorted_missed = sorted(uncolored_candidates.items(), key=lambda x: len(x[1]), reverse=True)
for sig, items in sorted_missed[:40]:
    print(f"\n[Count: {len(items):2d}] {sig}")
    sample_log, sample_text = items[0]
    print(f"  Example ({sample_log}): {sample_text}")
