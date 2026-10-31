import { readFile } from 'node:fs/promises'
import { basename, extname, resolve } from 'node:path'
import { NextResponse } from 'next/server'

const soundDirectory = resolve(process.cwd(), '../sounds')
const types: Record<string, string> = {
  '.mp3': 'audio/mpeg', '.wav': 'audio/wav', '.ogg': 'audio/ogg',
  '.m4a': 'audio/mp4', '.aac': 'audio/aac', '.webm': 'audio/webm',
}

export async function GET(_request: Request, { params }: { params: Promise<{ filename: string }> }) {
  const { filename } = await params
  const safeName = basename(filename)
  const contentType = types[extname(safeName).toLowerCase()]
  if (!contentType || safeName !== filename) return new NextResponse(null, { status: 404 })
  try {
    const data = await readFile(resolve(soundDirectory, safeName))
    return new NextResponse(data, { headers: { 'Content-Type': contentType, 'Cache-Control': 'no-store' } })
  } catch {
    return new NextResponse(null, { status: 404 })
  }
}
