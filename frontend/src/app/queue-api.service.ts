import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

export type TicketStatus = 'waiting' | 'called' | 'attending' | 'completed';
export type StationStatus = 'available' | 'occupied';

export interface Ticket {
  id: number;
  code: string;
  service: string;
  status: TicketStatus;
  station_number: number | null;
  created_at: string;
  called_at: string | null;
  finished_at: string | null;
}

export interface Station {
  number: number;
  status: StationStatus;
  current_ticket: Ticket | null;
}

export interface QueueState {
  stations: Station[];
  waiting: Ticket[];
  recent_calls: Ticket[];
  latest_call: Ticket | null;
  stats: {
    waiting: number;
    completed_today: number;
    created_today: number;
    available_stations: number;
  };
  server_time: string;
}

@Injectable({ providedIn: 'root' })
export class QueueApiService {
  private readonly http = inject(HttpClient);

  getState(): Observable<QueueState> {
    return this.http.get<QueueState>('/api/status');
  }

  createTicket(service: string): Observable<{ ticket: Ticket }> {
    return this.http.post<{ ticket: Ticket }>('/api/tickets', { service });
  }

  callNext(stationNumber: number): Observable<{ ticket: Ticket; station_number: number }> {
    return this.http.post<{ ticket: Ticket; station_number: number }>(
      '/api/stations/' + stationNumber + '/call',
      {},
    );
  }

  setStationStatus(
    stationNumber: number,
    status: StationStatus,
  ): Observable<{ status: StationStatus; next_ticket: Ticket | null }> {
    return this.http.patch<{ status: StationStatus; next_ticket: Ticket | null }>(
      '/api/stations/' + stationNumber + '/status',
      { status },
    );
  }
}
