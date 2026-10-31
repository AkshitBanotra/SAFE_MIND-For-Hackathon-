import { readdir } from 'node:fs/promises'
import { resolve } from 'node:path'
import { NextResponse } from 'next/server'

const soundDirectory = resolve(process.cwd(), '../sounds')
const supportedAudio = /\.(mp3|wav|ogg|m4a|aac|webm)$/i

export async function GET() {
  try {
    const files = await readdir(soundDirectory, { withFileTypes: true })
    return NextResponse.json(files.filter(file => file.isFile() && supportedAudio.test(file.name)).map(file => file.name).sort())
  } catch {
    return NextResponse.json([])
  }
}
