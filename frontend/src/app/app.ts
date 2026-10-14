import { CommonModule, DatePipe } from '@angular/common';
import { Component, OnDestroy, OnInit } from '@angular/core';
import { Subscription, interval } from 'rxjs';
import {
  QueueApiService,
  QueueState,
  Station,
  StationStatus,
  Ticket,
} from './queue-api.service';

@Component({
  imports: [CommonModule, DatePipe],
  selector: 'app-root',
  styleUrl: './app.css',
  templateUrl: './app.html',
})
export class App implements OnInit, OnDestroy {
  readonly services = ['Consulta general', 'Laboratorio', 'Farmacia', 'Imagenología'];
  selectedService = this.services[0];
  view: 'operation' | 'display' = 'operation';
  soundEnabled = false;
  creatingTicket = false;
  busyStation: number | null = null;
  notice = '';
  error = '';
  now = new Date();
  state: QueueState = {
    stations: [],
    waiting: [],
    recent_calls: [],
    latest_call: null,
    stats: { waiting: 0, completed_today: 0, created_today: 0, available_stations: 4 },
    server_time: '',
  };

  private readonly subscription = new Subscription();
  private hasInitialState = false;
  private lastAnnouncedId: number | null = null;
  private readonly lastStationStatuses = new Map<number, StationStatus>();
  private audioContext: AudioContext | null = null;

  constructor(private readonly api: QueueApiService) {}

  ngOnInit(): void {
    this.refreshState();
    this.subscription.add(interval(2500).subscribe(() => this.refreshState()));
  }

  ngOnDestroy(): void {
    this.subscription.unsubscribe();
    void this.audioContext?.close();
  }

  selectService(event: Event): void {
    this.selectedService = (event.target as HTMLSelectElement).value;
  }

  refreshState(): void {
    this.api.getState().subscribe({
      next: (nextState) => {
        const latest = nextState.latest_call;
        const newCall = this.hasInitialState && latest !== null && latest.id !== this.lastAnnouncedId;
        const changedStations = this.hasInitialState
          ? nextState.stations.filter((station) => {
              const previousStatus = this.lastStationStatuses.get(station.number);
              return previousStatus !== undefined && previousStatus !== station.status;
            })
          : [];
        const releasedForNextCall = newCall && latest?.station_number
          ? changedStations.find(
              (station) => station.number === latest.station_number && station.status === 'available',
            )
          : undefined;

        if (releasedForNextCall && latest) {
          this.announceMessage(
            'Ventanilla ' + releasedForNextCall.number + ' disponible. Turno ' + latest.code +
            ', favor de pasar a ventanilla ' + releasedForNextCall.number + '.',
          );
        }
        for (const station of changedStations) {
          if (station.number !== releasedForNextCall?.number) {
            this.announceStationStatus(station.number, station.status);
          }
        }
        if (newCall && latest && !releasedForNextCall) {
          this.announce(latest);
        }
        this.hasInitialState = true;
        this.lastAnnouncedId = latest?.id ?? null;
        for (const station of nextState.stations) {
          this.lastStationStatuses.set(station.number, station.status);
        }
        this.state = nextState;
        this.now = new Date();
        this.error = '';
      },
      error: () => {
        this.error = 'No pudimos conectar con el sistema de turnos.';
      },
    });
  }

  createTicket(): void {
    this.creatingTicket = true;
    this.notice = '';
    this.api.createTicket(this.selectedService).subscribe({
      next: ({ ticket }) => {
        this.creatingTicket = false;
        this.notice = 'Turno ' + ticket.code + ' generado. Ya puede pasar a la sala de espera.';
        this.refreshState();
      },
      error: (response) => {
        this.creatingTicket = false;
        this.error = response.error?.error || 'No se pudo generar el turno.';
      },
    });
  }

  callNext(station: Station): void {
    this.busyStation = station.number;
    this.notice = '';
    this.api.callNext(station.number).subscribe({
      next: ({ ticket }) => {
        this.busyStation = null;
        this.notice = ticket.code + ' asignado a la ventanilla ' + station.number + '.';
        this.refreshState();
      },
      error: (response) => {
        this.busyStation = null;
        this.error = response.error?.error || 'No se pudo llamar el siguiente turno.';
      },
    });
  }

  setStationStatus(station: Station, status: StationStatus): void {
    this.busyStation = station.number;
    this.notice = '';
    this.api.setStationStatus(station.number, status).subscribe({
      next: ({ next_ticket }) => {
        this.busyStation = null;
        this.notice = status === 'occupied'
          ? 'Ventanilla ' + station.number + ' en atención.'
          : next_ticket
            ? 'Ventanilla ' + station.number + ' disponible. Turno ' + next_ticket.code + ', favor de pasar.'
            : 'Ventanilla ' + station.number + ' disponible.';
        this.refreshState();
      },
      error: (response) => {
        this.busyStation = null;
        this.error = response.error?.error || 'No se pudo actualizar la ventanilla.';
      },
    });
  }

  toggleSound(): void {
    this.soundEnabled = !this.soundEnabled;
    if (!this.soundEnabled) return;

    try {
      this.audioContext = new AudioContext();
      void this.audioContext.resume();
      this.playBell();
      this.notice = 'Avisos activados para esta pantalla.';
    } catch {
      this.error = 'Este navegador no permite activar el sonido.';
      this.soundEnabled = false;
    }
  }

  private announce(ticket: Ticket): void {
    const destination = ticket.station_number
      ? 'favor de pasar a ventanilla ' + ticket.station_number
      : 'favor de acercarse a recepción';
    this.announceMessage('Turno ' + ticket.code + ', ' + destination + '.');
  }

  private announceStationStatus(number: number, status: StationStatus): void {
    const message = status === 'occupied'
      ? 'Ventanilla ' + number + ' ocupada.'
      : 'Ventanilla ' + number + ' disponible.';
    this.announceMessage(message);
  }

  private announceMessage(message: string): void {
    if (!this.soundEnabled) return;

    this.playBell();
    if ('speechSynthesis' in window) {
      const announcement = new SpeechSynthesisUtterance(message);
      announcement.lang = 'es-MX';
      announcement.rate = 0.88;
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(announcement);
    }
  }

  private playBell(): void {
    const context = this.audioContext;
    if (!context) return;
    const startAt = context.currentTime;
    [660, 880].forEach((frequency, index) => {
      const oscillator = context.createOscillator();
      const gain = context.createGain();
      oscillator.type = 'sine';
      oscillator.frequency.value = frequency;
      gain.gain.setValueAtTime(0.0001, startAt + index * 0.2);
      gain.gain.exponentialRampToValueAtTime(0.12, startAt + index * 0.2 + 0.035);
      gain.gain.exponentialRampToValueAtTime(0.0001, startAt + index * 0.2 + 0.32);
      oscillator.connect(gain);
      gain.connect(context.destination);
      oscillator.start(startAt + index * 0.2);
      oscillator.stop(startAt + index * 0.2 + 0.34);
    });
  }
}
