import { NextResponse } from 'next/server';
import { observationCatalog } from '../../../lib/data';

export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    return NextResponse.json(await observationCatalog());
  } catch (error) {
    console.error('Unable to load observation catalog', error);
    return NextResponse.json({ error: 'Observation catalog is unavailable.' }, { status: 500 });
  }
}
